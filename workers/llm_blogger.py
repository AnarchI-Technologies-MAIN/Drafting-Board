#!/usr/bin/env python3
"""Local MoE editorial orchestrator and generation-backlog builder."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests

from db import (
    claim_generation_jobs,
    ensure_schema,
    requeue_generation_job,
    serialize_ready_intakes,
    sha256_json,
    stage_generation_job,
    write_bot_run,
)
from pipeline_core import atomic_json, sha256_text, slugify, trim_text, utc_now, run_forever
from blog_loop.atomic_review import build_atomic_review_case
from blog_loop.local_verifier import make_local_verifier
from blog_loop.machine_adjudication import adjudicate_reviewed_artifact
from editorial_visual_request import VisualPurpose, build_editorial_visual_request
from editorial_visual_package import build_package
from blog_visual_materializer import materialize_package, validate_materialized_artifact
from blog_loop.review_execution import execute_atomic_review
from editorial_review_artifact import artifact_payload



ROOT = Path("/app")
DATA = ROOT / "data"
AUDIT_DIR = DATA / "generation_audits"
BOT_NAME = os.getenv("BOT_NAME", "llm-blogger")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "granite4:tiny-h")
MIN_POST_WORDS = int(os.getenv("MIN_POST_WORDS", "1400"))
MAX_POST_WORDS = int(os.getenv("MAX_POST_WORDS", "2800"))


def ollama_chat(messages: list[dict[str, str]], *, json_mode: bool, num_predict: int, temperature: float) -> tuple[str, dict[str, Any]]:
    payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "num_ctx": int(os.getenv("OLLAMA_CONTEXT_TOKENS", "8192")),
            "num_predict": num_predict,
            "num_thread": int(os.getenv("OLLAMA_NUM_THREAD", "6")),
        },
        "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
    }
    if json_mode:
        payload["format"] = "json"
    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json=payload,
        timeout=int(os.getenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "900")),
    )
    response.raise_for_status()
    raw = response.json()
    return raw.get("message", {}).get("content", "").strip(), {
        "model": raw.get("model", OLLAMA_MODEL),
        "total_duration": raw.get("total_duration"),
        "load_duration": raw.get("load_duration"),
        "prompt_eval_count": raw.get("prompt_eval_count"),
        "eval_count": raw.get("eval_count"),
    }


def packets_by_type(bundle: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for packet in bundle.get("packets", []):
        grouped.setdefault(packet["packet_type"], []).append(packet)
    return grouped


def editorial_context(bundle: dict[str, Any]) -> dict[str, Any]:
    grouped = packets_by_type(bundle)
    sources = []
    intake = bundle["intake"]
    relevance_keywords = (intake.get("seo_plan") or {}).get("keyword_family", [])
    for packet in grouped.get("source_document", []):
        payload = packet["payload"]
        page = payload.get("page") or {}
        stored_relevance = payload.get("relevance") or {}
        source = {
            "relevance": stored_relevance
            if stored_relevance.get("policy_version") == 2
            else {"passed": False, "score": stored_relevance.get("score", 0), "reason": "stale_relevance_policy"},
            "packet_id": packet["id"],
            "title": payload.get("title"),
            "url": payload.get("url"),
            "provider": payload.get("provider"),
            "metrics": payload.get("metrics", {}),
            "evidence_excerpt": trim_text(page.get("excerpt") or payload.get("search_snippet", ""), 1800),
        }
        sources.append(source)
    sources = [
        source
        for source in sources
        if source.get("url") and source.get("evidence_excerpt") and source.get("relevance", {}).get("passed")
    ]
    sources.sort(key=lambda source: source.get("relevance", {}).get("score", 0), reverse=True)
    sources = sources[:12]
    seo_packets = grouped.get("seo_enrichment", [])
    seo = seo_packets[-1]["payload"] if seo_packets else bundle["intake"].get("seo_plan", {})
    affiliates = [packet["payload"] for packet in grouped.get("affiliate_opportunity", [])]
    ads = [packet["payload"] for packet in grouped.get("ad_campaign_candidate", [])]
    return {
        "intake": bundle["intake"],
        "sources": sources,
        "seo": seo,
        "verified_affiliates": [item for item in affiliates if item.get("verification_status") == "verified"],
        "commercial_research": [
            {key: item.get(key) for key in ("name", "category", "relevance_score", "verification_status", "discovery_evidence")}
            for item in affiliates
        ],
        "ad_candidates": ads,
        "image_references": [packet["payload"] for packet in grouped.get("source_image_reference", [])][:12],
    }


def fallback_plan(context: dict[str, Any]) -> dict[str, Any]:
    query = context["intake"]["query"]
    return {
        "seo_title": trim_text(query.title(), 68),
        "summary": trim_text(f"A source-backed engineering guide to diagnosing, implementing, and verifying {query}.", 155),
        "thesis": f"Treat {query} as a measurable systems problem, not a collection of folklore fixes.",
        "outline": [
            "Problem signature and operational impact",
            "System model and root causes",
            "Evidence-backed diagnosis",
            "Implementation walkthrough",
            "Verification and observability",
            "Trade-offs and failure modes",
            "Actionable checklist",
        ],
        "hashtags": context.get("seo", {}).get("hashtags", [])[:10],
    }


def build_plan(context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if os.getenv("MOE_PLANNER_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        return fallback_plan(context), {"provider": "deterministic-evidence-plan"}
    compact = {
        "query": context["intake"]["query"],
        "cluster": context["intake"]["topic_cluster"],
        "intent": context["intake"]["search_intent"],
        "seo": context["seo"],
        "sources": [{key: source.get(key) for key in ("packet_id", "title", "url", "provider", "metrics", "evidence_excerpt")} for source in context["sources"]],
        "commercial_research": context["commercial_research"],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You are the planning expert in a local technical editorial system. Return valid JSON only. "
                "Design a people-first, original, source-grounded engineering article. Do not invent benchmarks, "
                "product experience, affiliate relationships, or facts. The title must be descriptive and concise, "
                "not clickbait or keyword-stuffed. Every factual section must map to provided source URLs."
            ),
        },
        {
            "role": "user",
            "content": (
                "Create an editorial plan with keys seo_title, summary, thesis, reader_outcome, outline, "
                "source_map, claims_to_avoid, hashtags, and verification_steps. seo_title <= 70 characters; "
                "summary <= 160. Require diagnosis, implementation, code or commands, validation, trade-offs, "
                "and a clear disclosure if a verified affiliate link is later used.\n\nSOURCE BUNDLE:\n"
                + json.dumps(compact, ensure_ascii=False, default=str)
            ),
        },
    ]
    raw, metrics = ollama_chat(messages, json_mode=True, num_predict=1200, temperature=0.25)
    try:
        plan = json.loads(raw)
        if not isinstance(plan, dict):
            raise ValueError("plan is not an object")
    except Exception:
        plan = fallback_plan(context)
    plan["seo_title"] = trim_text(str(plan.get("seo_title") or context["intake"]["query"].title()), 70)
    plan["summary"] = trim_text(str(plan.get("summary") or fallback_plan(context)["summary"]), 160)
    return plan, metrics


SECTION_SPECS = [
    ("Problem signature and operational impact", "Define observable symptoms, stakes, boundaries, and what a false positive looks like."),
    ("System model and likely root causes", "Build a causal mental model and separate primary causes from amplifiers."),
    ("Evidence-backed diagnostic workflow", "Give an ordered investigation that preserves evidence and narrows hypotheses."),
    ("Implementation walkthrough", "Give safe implementation steps and include one complete fenced code or command example."),
    ("Verification and observability", "Explain tests, measurements, rollback signals, and how to prove the change worked."),
    ("Trade-offs and failure modes", "Cover costs, limitations, edge cases, and conditions where another approach is better."),
    ("Production checklist", "End with a concrete, prioritized checklist an engineering team can execute."),
]


def clean_section(text: str, context: dict[str, Any]) -> str:
    text = text.strip()
    if re.match(r"^```markdown\s*\n", text, flags=re.IGNORECASE) and re.search(r"\n```\s*$", text):
        text = re.sub(r"^```markdown\s*\n", "", text, count=1, flags=re.IGNORECASE)
        text = re.sub(r"\n```\s*$", "", text, count=1)
    text = re.sub(r"^#{1,6}\s+.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\*\*(?:word count|h2 sections?|source citations?).*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    allowed = source_urls(context)

    def keep_supported(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2)
        return match.group(0) if url.rstrip("/") in allowed else label

    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", keep_supported, text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def write_section(
    context: dict[str, Any], plan: dict[str, Any], heading: str, assignment: str, section_index: int
) -> tuple[str, dict[str, Any]]:
    sources = context["sources"]
    selected = [sources[(section_index + offset) % len(sources)] for offset in range(min(3, len(sources)))]
    source_lines = []
    for index, source in enumerate(selected, start=1):
        source_lines.append(
            f"S{index}: {source['title']}\nURL: {source['url']}\nEVIDENCE: {trim_text(source['evidence_excerpt'], 700)}"
        )
    messages = [
        {
            "role": "system",
            "content": (
                "You are one specialist in a section-by-section local MoE editorial pipeline. Write only the assigned "
                "section body, without a heading, title, conclusion, references list, or word-count claim. Be precise "
                "and useful to experienced engineers. Synthesize and do not copy source language. Cite evidence inline "
                "using the exact supplied Markdown URLs only. Mark deductions as inference. Never invent measurements, "
                "hands-on testing, vulnerabilities, product capabilities, database objects, commands, APIs, or affiliate "
                "relationships. Begin immediately with useful prose. Do not restate the query, section title, task, or "
                "source list. Ignore site navigation, release banners, and version menus inside excerpts."
            ),
        },
        {
            "role": "user",
            "content": (
                f"The full article addresses {context['intake']['query']}. Its thesis is: {plan['thesis']}\n"
                f"Write the section titled {heading}. {assignment}\n"
                "Write 230-340 substantive words. Use short paragraphs and lists when useful. "
                "For the implementation section, include a complete fenced code or command block with comments.\n\n"
                "Use these bounded facts without reproducing this list:\n" + "\n\n".join(source_lines)
            ),
        },
    ]
    raw, metrics = ollama_chat(messages, json_mode=False, num_predict=760, temperature=0.48)
    section = clean_section(raw, context)
    citations = re.findall(r"\[[^\]]+\]\((https?://[^)]+)\)", section)
    if not any(url.rstrip("/") in source_urls(context) for url in citations):
        source = selected[0]
        section += f"\n\nEvidence basis: [{source['title']}]({source['url']})."
    return section, metrics


def write_draft(context: dict[str, Any], plan: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    parts = [f"# {plan['seo_title']}", plan["summary"]]
    metrics: list[dict[str, Any]] = []
    for index, (heading, assignment) in enumerate(SECTION_SPECS):
        section, section_metrics = write_section(context, plan, heading, assignment, index)
        parts.extend([f"## {heading}", section])
        metrics.append({"section": heading, **section_metrics})
    return "\n\n".join(parts).strip(), metrics


def source_urls(context: dict[str, Any]) -> set[str]:
    return {source["url"].rstrip("/") for source in context["sources"] if source.get("url")}


def code_fence_quality(body: str) -> dict[str, Any]:
    open_fence = False
    completed = 0
    invalid = False
    content_lines = 0
    for line in body.splitlines():
        stripped = line.strip()
        if not open_fence and re.match(r"^```[A-Za-z0-9_+.-]*\s*$", stripped):
            open_fence = True
            content_lines = 0
        elif open_fence and stripped == "```":
            invalid = invalid or content_lines == 0
            completed += 1
            open_fence = False
        elif open_fence and stripped.startswith("```"):
            invalid = True
        elif open_fence:
            if re.match(r"^#{1,6}\s+", stripped):
                invalid = True
            if stripped:
                content_lines += 1
    return {"completed": completed, "valid": not open_fence and not invalid}


def quality_check(body: str, context: dict[str, Any], title: str) -> dict[str, Any]:
    words = re.findall(r"\b[\w'-]+\b", body)
    citations = re.findall(r"\[[^\]]+\]\((https?://[^)]+)\)", body)
    allowed = source_urls(context)
    supported = [url for url in citations if url.rstrip("/") in allowed]
    headings = len(re.findall(r"^##\s+", body, re.MULTILINE))
    fences = code_fence_quality(body)
    code_blocks = fences["completed"]
    excerpt_blob = " ".join(source.get("evidence_excerpt", "") for source in context["sources"])
    largest_copy = SequenceMatcher(None, body.lower(), excerpt_blob.lower(), autojunk=True).find_longest_match(
        0, len(body), 0, len(excerpt_blob)
    ).size
    copied_ratio = round(largest_copy / max(1, len(body)), 4)
    failures = []
    if len(words) < MIN_POST_WORDS:
        failures.append(f"word count {len(words)} is below {MIN_POST_WORDS}")
    if len(words) > MAX_POST_WORDS + 300:
        failures.append(f"word count {len(words)} exceeds {MAX_POST_WORDS + 300}")
    if headings < 5:
        failures.append(f"only {headings} H2 sections")
    if code_blocks < 1:
        failures.append("no complete code or command block")
    if not fences["valid"]:
        failures.append("malformed or empty fenced code block")
    if len(set(supported)) < min(3, len(allowed)):
        failures.append(f"only {len(set(supported))} supported source citations")
    if any(url.rstrip("/") not in allowed for url in citations):
        failures.append("contains citation URLs not present in the source bundle")
    if copied_ratio > 0.12:
        failures.append(f"source-overlap ratio {copied_ratio} is too high")
    if len(title) > 70:
        failures.append("SEO title exceeds 70 characters")
    prompt_leaks = re.findall(
        r"(?im)^\*{0,2}(?:primary query|assigned section|substantive words|evidence sources|goal):?\*{0,2}\s*$",
        body,
    )
    if prompt_leaks:
        failures.append("contains internal prompt labels")
    normalized_lines = [re.sub(r"\W+", " ", line.lower()).strip() for line in body.splitlines()]
    repeated = {line for line in normalized_lines if len(line) >= 45 and normalized_lines.count(line) >= 3}
    if repeated:
        failures.append("contains repeated boilerplate lines")
    cluster = (context.get("intake") or {}).get("topic_cluster")
    if cluster == "database-performance":
        postgres_identifiers = set(re.findall(r"\bpg_[a-z0-9_]+\b", body.lower()))
        source_lower = excerpt_blob.lower()
        unsupported_identifiers = sorted(identifier for identifier in postgres_identifiers if identifier not in source_lower)
        if unsupported_identifiers:
            failures.append("PostgreSQL identifiers absent from evidence: " + ", ".join(unsupported_identifiers[:8]))
        if re.search(r"(?i)\bLOCK\s+(?:INDEX|SEQUENCE)\b", body):
            failures.append("contains unsupported PostgreSQL LOCK INDEX/SEQUENCE syntax")
    return {
        "passed": not failures,
        "failures": failures,
        "word_count": len(words),
        "h2_count": headings,
        "code_block_count": code_blocks,
        "code_fences_valid": fences["valid"],
        "citation_count": len(citations),
        "supported_unique_citations": len(set(supported)),
        "largest_source_overlap_ratio": copied_ratio,
        "checked_at": utc_now(),
    }


def semantic_review(body: str, context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = [
        {
            "title": source["title"],
            "url": source["url"],
            "excerpt": trim_text(source["evidence_excerpt"], 900),
        }
        for source in context["sources"][:8]
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "You are the independent technical fact-checker in a local editorial pipeline. Return JSON only. "
                "Reject any invented command, identifier, benchmark, API, capability, causal claim, obsolete guidance, "
                "unsafe recommendation, prompt leakage, or material repetition. Treat the supplied excerpts as the "
                "only factual evidence. Do not reward fluency or length."
            ),
        },
        {
            "role": "user",
            "content": (
                "Review the article against the evidence. Return keys passed (boolean), score (0-100), "
                "critical_issues (array), unsupported_claims (array), and notes (array). passed may be true only "
                "when score is at least 82 and both issue arrays are empty.\n\nEVIDENCE:\n"
                + json.dumps(evidence, ensure_ascii=False)
                + "\n\nARTICLE:\n"
                + body
            ),
        },
    ]
    raw, metrics = ollama_chat(messages, json_mode=True, num_predict=900, temperature=0.1)
    try:
        review = json.loads(raw)
        if not isinstance(review, dict):
            raise ValueError("review is not an object")
    except Exception as exc:
        review = {"passed": False, "score": 0, "critical_issues": [f"unparseable semantic review: {exc}"], "unsupported_claims": [], "notes": []}
    score = int(review.get("score") or 0)
    critical = review.get("critical_issues") if isinstance(review.get("critical_issues"), list) else ["invalid critical_issues field"]
    unsupported = review.get("unsupported_claims") if isinstance(review.get("unsupported_claims"), list) else ["invalid unsupported_claims field"]
    review["passed"] = bool(review.get("passed") and score >= 82 and not critical and not unsupported)
    review["score"] = score
    review["critical_issues"] = critical[:12]
    review["unsupported_claims"] = unsupported[:12]
    review["reviewed_at"] = utc_now()
    return review, metrics


def targeted_repair(
    body: str, context: dict[str, Any], plan: dict[str, Any], failures: list[str]
) -> tuple[str, list[dict[str, Any]]]:
    """Repair missing structure additively; never ask a small model to rewrite 2,000 words."""
    metrics: list[dict[str, Any]] = []
    repaired = body
    words = len(re.findall(r"\b[\w'-]+\b", repaired))
    addition = 0
    while words < MIN_POST_WORDS and addition < 3:
        heading = "Operational runbook" if addition == 0 else f"Additional production consideration {addition + 1}"
        section, section_metrics = write_section(
            context,
            plan,
            heading,
            "Add non-repetitive, source-grounded operational detail that closes gaps in the current guide.",
            len(SECTION_SPECS) + addition,
        )
        repaired += f"\n\n## {heading}\n\n{section}"
        metrics.append({"repair_section": heading, **section_metrics})
        words = len(re.findall(r"\b[\w'-]+\b", repaired))
        addition += 1
    if repaired.count("```") // 2 < 1:
        section, section_metrics = write_section(
            context,
            plan,
            "Implementation example",
            "Provide one complete, conservative fenced code or command example and explain how to validate it.",
            len(SECTION_SPECS) + addition,
        )
        repaired += f"\n\n## Implementation example\n\n{section}"
        metrics.append({"repair_section": "Implementation example", **section_metrics})
    return repaired, metrics


def generate_job(job: dict[str, Any]) -> dict[str, Any]:
    bundle = job["source_bundle"]
    context = editorial_context(bundle)
    if len(context["sources"]) < 2:
        return {
            "state": "quality_hold",
            "quality": {"passed": False, "failures": ["fewer than two usable source excerpts"]},
            "error": "insufficient evidence after serialization",
        }
    plan, planner_metrics = build_plan(context)
    draft, writer_metrics = write_draft(context, plan)
    draft = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", draft.strip(), flags=re.IGNORECASE)
    quality = quality_check(draft, context, plan["seo_title"])
    repair_metrics: list[dict[str, Any]] = []
    if not quality["passed"]:
        repaired, repair_metrics = targeted_repair(draft, context, plan, quality["failures"])
        repaired_quality = quality_check(repaired, context, plan["seo_title"])
        repaired_quality["initial_failures"] = quality["failures"]
        draft, quality = repaired, repaired_quality
    verifier_metrics = None
    semantic = {"passed": False, "score": 0, "critical_issues": ["deterministic QA did not pass"], "unsupported_claims": []}
    if quality["passed"]:
        semantic, verifier_metrics = semantic_review(draft, context)
        quality["semantic_review"] = semantic
        if not semantic["passed"]:
            quality["passed"] = False
            quality["failures"].append("independent semantic review did not pass")
    seo = {
        "title": plan["seo_title"],
        "meta_description": plan["summary"],
        "primary_query": context["intake"]["query"],
        "topic_cluster": context["intake"]["topic_cluster"],
        "hashtags": list(dict.fromkeys(plan.get("hashtags", []) + context.get("seo", {}).get("hashtags", [])))[:12],
        "schema_type": "BlogPosting",
        "source_urls": sorted(source_urls(context)),
        "image_references": context["image_references"],
    }
    atomic_review = {
        "attempted": False,
        "text_review_passed": False,
        "artifact_digest": None,
        "artifact": None,
        "fracture_claim_ids": [],
        "verifier_observations": [],
        "publication_authority": "NONE",
        "human_adjudication_authority": "NONE",
    }

    if quality["passed"]:
        case = build_atomic_review_case(
            article_text=draft,
            source_bundle=bundle,
        )

        observations = []

        verifier = make_local_verifier(
            chat_function=ollama_chat,
            observations=observations,
        )

        run_id = (
            "blog-review-"
            + str(job["id"])
            + "-"
            + sha256_text(draft).split(":", 1)[-1][:16]
        )

        execution = execute_atomic_review(
            case=case,
            verifier=verifier,
            verifier_model=OLLAMA_MODEL,
            verifier_run_id=run_id,
        )

        reviewed = execution.reviewed_artifact
        visual_request = build_editorial_visual_request(
            artifact=reviewed,
            visual_purpose=VisualPurpose.FACTUAL,
            visual_instruction=(
                "Create a source-faithful factual visual representing the reviewed article claims without adding, strengthening, or changing any claim.",
            ),
            bound_claim_ids=reviewed.material_claim_ids,
        )
        visual_package = build_package(
            artifact=reviewed,
            request=visual_request,
        )
        visual_artifact = materialize_package(visual_package)
        visual_errors = validate_materialized_artifact(
            visual_artifact,
            visual_package,
        )
        if visual_errors:
            raise ValueError(
                "materialized visual validation failed: "+
                "; ".join(visual_errors)
            )
        machine_adjudication = adjudicate_reviewed_artifact(reviewed)

        atomic_review = {
            "attempted": True,
            "text_review_passed": (
                execution.text_review_passed
            ),
            "artifact_digest": (
                reviewed.artifact_digest
            ),
            "artifact": artifact_payload(
                reviewed
            ),
            "fracture_claim_ids": [
                item.claim_id
                for item
                in execution.article_verification.fractures
            ],
            "verifier_observations": [
                item.metrics
                for item in observations
            ],
            "publication_authority": "NONE",
            "human_adjudication_authority": "NONE",
            "machine_adjudication": {
                "schema_version": machine_adjudication.schema_version,
                "artifact_digest": machine_adjudication.artifact_digest,
                "disposition": machine_adjudication.disposition,
                "fracture_claim_ids": list(
                    machine_adjudication.fracture_claim_ids
                ),
                "receipt": machine_adjudication.receipt,
                "bucket": machine_adjudication.bucket,
                "human_adjudication_authority": "NONE",
                "publication_authority": "NONE",
            },
        }

        quality["atomic_review"] = atomic_review

        if not execution.text_review_passed:
            quality["passed"] = False
            quality["failures"].append(
                "atomic claim review did not pass"
            )

    else:
        quality["atomic_review"] = atomic_review

    return {
        "state": "quality_hold",
        "title": plan["seo_title"],
        "slug": f"{slugify(plan['seo_title'])}-{job['id']}",
        "summary": plan["summary"],
        "body": draft,
        "seo": seo,
        "quality": quality,
        "model_lineage": {
            "provider": "local-ollama",
            "model": OLLAMA_MODEL,
            "orchestration": [
                "evidence-plan",
                "section-specialists",
                "deterministic-assembly",
                "deterministic-quality-gate",
                "targeted-repair",
                "atomic-claim-extraction",
                "eligible-evidence-binding",
                "proposal-only-local-verifier",
                "deterministic-verifier-adapter",
                "reviewed-article-artifact",
            ],
            "source_bundle_digest": sha256_json(bundle),
            "plan_digest": sha256_json(plan),
            "draft_digest": sha256_text(draft),
            "planner_metrics": planner_metrics,
            "writer_metrics": writer_metrics,
            "repair_metrics": repair_metrics,
            "verifier_metrics": verifier_metrics,
            "atomic_review_artifact_digest": (
                atomic_review["artifact_digest"]
            ),
            "generated_at": utc_now(),
        },
        "error": (
            "awaiting human adjudication"
            if atomic_review["text_review_passed"]
            else "; ".join(quality["failures"])
        ),
    }


def cycle() -> None:
    new_jobs = serialize_ready_intakes(int(os.getenv("SERIALIZE_BATCH_SIZE", "50")), BOT_NAME)
    jobs = claim_generation_jobs(int(os.getenv("GENERATION_BATCH_SIZE", "1")))
    results = []
    for job in jobs:
        try:
            result = generate_job(job)
            stage_generation_job(job["id"], result)
            results.append({"job_id": job["id"], "state": result["state"], "quality": result.get("quality")})
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            requeue_generation_job(job["id"], error)
            results.append({"job_id": job["id"], "state": "requeued", "error": error})
    audit = {
        "schema": "anarchi.generation-cycle.v1",
        "captured_at": utc_now(),
        "model": OLLAMA_MODEL,
        "new_generation_jobs": new_jobs,
        "generation_results": results,
    }
    if new_jobs or jobs:
        filename = datetime.now(timezone.utc).strftime("generation_audit_%Y%m%dT%H%M%SZ.json")
        atomic_json(AUDIT_DIR / filename, audit)
    write_bot_run(BOT_NAME, "generation_cycle", audit)
    print(f"[{BOT_NAME}] queued {len(new_jobs)} bundles and processed {len(jobs)} generation jobs", flush=True)


def main() -> None:
    ensure_schema()
    run_forever(BOT_NAME, int(os.getenv("BOT_INTERVAL_SECONDS", "300")), cycle)


if __name__ == "__main__":
    main()
