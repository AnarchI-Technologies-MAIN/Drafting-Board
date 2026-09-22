#!/usr/bin/env python3
"""Evidence-backed, high-value engineering query intake.

This worker records why a query entered the system. Scores are explicitly proxies
derived from public engagement signals and curated commercial/problem intent; they
are never represented as measured keyword volume or CPC.
"""

from __future__ import annotations

import json
import os
import html
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db import append_packet, ensure_schema, upsert_intake, write_bot_run
from pipeline_core import (
    PROBLEM_TERMS,
    atomic_json,
    clamp,
    request_json,
    run_forever,
    signal_score,
    keywords_from_text,
    term_density_score,
    topic_relevance,
    utc_now,
)


ROOT = Path("/app")
DATA = ROOT / "data"
POLICY_PATH = DATA / "config" / "intake_policy.json"
AUDIT_DIR = DATA / "search_audits"
BOT_NAME = os.getenv("BOT_NAME", "research-bot")


def load_policy() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def collect_hacker_news() -> list[dict[str, Any]]:
    data = request_json(
        "https://hn.algolia.com/api/v1/search",
        params={"tags": "front_page", "hitsPerPage": 100},
    )
    observations = []
    for hit in data.get("hits", []):
        title = (hit.get("title") or "").strip()
        if not title:
            continue
        observations.append(
            {
                "source": "hacker-news-algolia",
                "title": title,
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                "engagement": int(hit.get("points") or 0) + 2 * int(hit.get("num_comments") or 0),
                "points": int(hit.get("points") or 0),
                "comments": int(hit.get("num_comments") or 0),
                "observed_at": utc_now(),
            }
        )
    return observations


def collect_stack_overflow() -> list[dict[str, Any]]:
    data = request_json(
        "https://api.stackexchange.com/2.3/questions",
        params={
            "site": "stackoverflow",
            "pagesize": 100,
            "order": "desc",
            "sort": "hot",
            "filter": "default",
        },
    )
    observations = []
    for item in data.get("items", []):
        title = (item.get("title") or "").strip()
        observations.append(
            {
                "source": "stackoverflow-api",
                "title": title,
                "url": item.get("link", ""),
                "tags": item.get("tags", []),
                "engagement": int(item.get("view_count") or 0) + 20 * int(item.get("score") or 0),
                "views": int(item.get("view_count") or 0),
                "score": int(item.get("score") or 0),
                "answers": int(item.get("answer_count") or 0),
                "observed_at": utc_now(),
            }
        )
    return observations


def gather_signals() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    signals: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for source_name, collector in (
        ("hacker-news-algolia", collect_hacker_news),
        ("stackoverflow-api", collect_stack_overflow),
    ):
        try:
            signals.extend(collector())
        except Exception as exc:
            errors.append({"source": source_name, "error": f"{type(exc).__name__}: {exc}"[:500]})
    return signals, errors


def score_cluster(cluster: dict[str, Any], signals: list[dict[str, Any]]) -> dict[str, Any]:
    keywords = [str(value).lower() for value in cluster["keywords"]]
    matches = []
    for signal in signals:
        haystack = " ".join([signal.get("title", ""), " ".join(signal.get("tags", []))]).lower()
        overlap = [keyword for keyword in keywords if keyword in haystack]
        if overlap:
            copy = dict(signal)
            copy["matched_keywords"] = overlap
            matches.append(copy)
    matches.sort(key=lambda value: value.get("engagement", 0), reverse=True)
    source_breadth = len({match["source"] for match in matches})
    engagement = sum(match.get("engagement", 0) for match in matches[:8])
    traffic = clamp(45 + 0.45 * signal_score(engagement, 250_000) + 7 * source_breadth)
    trend = clamp(40 + 5 * min(len(matches), 8) + 8 * source_breadth)
    value = clamp(float(cluster["commercial_base"]))
    problem = clamp(float(cluster["problem_base"]))
    return {
        "traffic_score": traffic,
        "trend_score": trend,
        "value_score": value,
        "problem_score": problem,
        "matches": matches[:8],
        "source_breadth": source_breadth,
    }


def query_evidence(
    cluster: dict[str, Any],
    query: str,
    signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return only public signals that independently pass the query relevance gate."""
    evidence: list[dict[str, Any]] = []

    for signal in signals:
        text = " ".join(
            [
                str(signal.get("title") or ""),
                " ".join(str(tag) for tag in signal.get("tags", [])),
            ]
        )
        query_keywords = keywords_from_text(
            query,
            [str(value) for value in cluster.get("keywords", [])],
        )
        relevance = topic_relevance(
            text,
            query,
            query_keywords,
        )
        if not relevance["passed"]:
            continue

        copy = dict(signal)
        copy["query_relevance"] = relevance
        evidence.append(copy)

    evidence.sort(key=lambda value: value.get("engagement", 0), reverse=True)
    return evidence[:8]


def make_candidate(cluster: dict[str, Any], query: str, scored: dict[str, Any]) -> dict[str, Any]:
    query_problem = term_density_score(query, PROBLEM_TERMS, base=scored["problem_score"] - 18, per_hit=6)
    problem = clamp(max(scored["problem_score"], query_problem))
    total = clamp(
        0.31 * scored["traffic_score"]
        + 0.29 * scored["value_score"]
        + 0.25 * problem
        + 0.15 * scored["trend_score"]
    )
    tier = 5 if total >= 88 else 4 if total >= 78 else 3
    keywords = [query] + cluster["keywords"][:8]
    return {
        "query": query,
        "topic_cluster": cluster["id"],
        "search_intent": cluster["intent"],
        "tier": tier,
        "traffic_score": scored["traffic_score"],
        "value_score": scored["value_score"],
        "problem_score": problem,
        "trend_score": scored["trend_score"],
        "total_score": total,
        "evidence": scored["matches"],
        "seo_plan": {
            "primary_query": query,
            "secondary_keywords": cluster["keywords"][:8],
            "intent": cluster["intent"],
            "title_pattern": f"{query}: evidence, diagnosis, implementation, and verification",
            "required_sections": [
                "symptoms and impact",
                "root-cause model",
                "step-by-step implementation",
                "verification and observability",
                "trade-offs and failure modes",
            ],
            "people_first_gate": True,
            "scoring_basis": "public engagement proxies plus curated engineering/commercial intent",
            "measurement_disclaimer": "not measured search volume or CPC",
            "keyword_family": keywords,
        },
    }


def signal_candidates(cluster: dict[str, Any], scored: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    """Turn observed signals into candidates only when they prove query relevance.

    Cluster keyword overlap is discovery evidence, not sufficient editorial evidence.
    Every observed signal must independently relate to at least one declared cluster
    query before it can become a candidate.
    """
    candidates: list[dict[str, Any]] = []
    cluster_queries = [str(query) for query in cluster.get("queries", [])]
    query_keywords = keywords_from_text(
        " ".join(cluster_queries),
        [str(value) for value in cluster.get("keywords", [])],
    )

    for signal in scored["matches"][:limit]:
        title = html.unescape(str(signal.get("title") or ""))
        title = re.sub(r"^(show|ask|tell) hn:\s*", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s+", " ", title).strip(" -:?")
        if not 18 <= len(title) <= 170:
            continue

        signal_text = " ".join(
            [
                title,
                " ".join(str(tag) for tag in signal.get("tags", [])),
            ]
        )

        relevance_matches = []
        for query in cluster_queries:
            relevance = topic_relevance(
                signal_text,
                query,
                query_keywords,
            )
            if relevance["passed"]:
                relevance_matches.append(
                    {
                        "query": query,
                        "relevance": relevance,
                    }
                )

        if not relevance_matches:
            continue

        relevance_matches.sort(
            key=lambda item: item["relevance"]["score"],
            reverse=True,
        )
        best_relevance = relevance_matches[0]

        evidence = dict(signal)
        evidence["query_relevance"] = dict(best_relevance["relevance"])
        evidence["query_relevance"]["matched_query"] = best_relevance["query"]

        individual = dict(scored)
        individual["matches"] = [evidence]
        individual["trend_score"] = clamp(
            max(
                scored["trend_score"],
                58 + signal_score(int(signal.get("engagement") or 0), 50_000) * 0.34,
            )
        )

        candidate = make_candidate(cluster, title, individual)
        candidate["origin"] = "observed-public-problem-signal"
        candidate["seo_plan"]["signal_source"] = signal.get("source")
        candidate["seo_plan"]["observed_signal_query"] = best_relevance["query"]
        candidates.append(candidate)

    return candidates
def cycle() -> None:
    policy = load_policy()
    signals, errors = gather_signals()
    candidates = []
    for cluster in policy["clusters"]:
        scored = score_cluster(cluster, signals)
        for query in cluster["queries"]:
            evidence = query_evidence(cluster, query, signals)
            if not evidence:
                continue

            query_scored = dict(scored)
            query_scored["matches"] = evidence
            candidate = make_candidate(cluster, query, query_scored)

            if (
                candidate["total_score"] >= policy["minimum_total_score"]
                and candidate["value_score"] >= policy["minimum_value_score"]
                and candidate["problem_score"] >= policy["minimum_problem_score"]
            ):
                candidates.append(candidate)
        candidates.extend(
            signal_candidates(
                cluster,
                scored,
                int(policy.get("max_signal_queries_per_cluster", 4)),
            )
        )
    candidates.sort(key=lambda item: item["total_score"], reverse=True)
    max_new = int(os.getenv("MAX_NEW_QUERIES_PER_CYCLE", policy["max_new_queries_per_cycle"]))
    selected = []
    refreshed = 0
    inserted = 0
    intake_ids = []
    for candidate in candidates:
        intake_id, was_inserted = upsert_intake(candidate)
        if not was_inserted:
            refreshed += 1
            continue
        inserted += 1
        selected.append(candidate)
        intake_ids.append(intake_id)
        append_packet(
            intake_id,
            "search_intake",
            BOT_NAME,
            {
                "schema": "anarchi.search-intake.v1",
                "query": candidate["query"],
                "scores": {key: candidate[key] for key in ("traffic_score", "value_score", "problem_score", "trend_score", "total_score", "tier")},
                "evidence": candidate["evidence"],
                "seo_plan": candidate["seo_plan"],
                "captured_at": utc_now(),
            },
        )
        if inserted >= max_new:
            break
    audit = {
        "schema": "anarchi.search-audit.v1",
        "captured_at": utc_now(),
        "policy": str(POLICY_PATH),
        "scoring_note": policy["scoring_note"],
        "signal_count": len(signals),
        "source_errors": errors,
        "selected": selected,
        "intake_ids": intake_ids,
        "new_intake_count": inserted,
        "existing_candidates_refreshed": refreshed,
    }
    filename = datetime.now(timezone.utc).strftime("search_audit_%Y%m%dT%H%M%SZ.json")
    atomic_json(AUDIT_DIR / filename, audit)
    write_bot_run(BOT_NAME, "search_intake", audit, "degraded" if errors and not signals else "ok")
    print(f"[{BOT_NAME}] recorded {inserted} new tiered queries after refreshing {refreshed} existing candidates from {len(signals)} public signals", flush=True)


def main() -> None:
    ensure_schema()
    run_forever(BOT_NAME, int(os.getenv("BOT_INTERVAL_SECONDS", "21600")), cycle)


if __name__ == "__main__":
    main()
