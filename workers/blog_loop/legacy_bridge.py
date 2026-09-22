"""Legacy editorial packet normalization into Blog Loop contracts.

This module is deliberately pure.

It does not:
- connect to PostgreSQL,
- call network providers,
- mutate intake or generation state,
- create publication authority,
- create factual authority,
- convert legacy affiliate opportunities into eligible commerce.

Its only job is to translate already-materialized legacy packet bundles into
the newer deterministic receipt vocabulary without increasing semantic
strength.
"""

from __future__ import annotations

import html
import re
from typing import Any

from .core import canonical_digest, valid_timestamp
from .editorial import (
    build_article_input,
    build_evidence_receipt,
    build_keyword_receipt,
    build_niche_assessment,
    build_seo_plan,
    build_topic_packet,
)


BRIDGE_SCHEMA = "anarchi.legacy-blog-normalization.v1"
BRIDGE_IMPLEMENTATION = "deterministic-legacy-packet-normalizer-v1"

UNKNOWN_FRESHNESS_REQUIREMENT = {
    "max_age_days": None,
    "policy_state": "NOT_DEFINED",
}


class LegacyNormalizationError(ValueError):
    """Raised when the legacy bundle cannot safely earn the new contracts."""


def _packet_payloads(
    bundle: dict[str, Any],
    packet_type: str,
) -> list[dict[str, Any]]:
    packets = bundle.get("packets")

    if not isinstance(packets, list):
        raise LegacyNormalizationError("source bundle packets must be a list")

    found: list[dict[str, Any]] = []

    for packet in packets:
        if not isinstance(packet, dict):
            continue

        if packet.get("packet_type") != packet_type:
            continue

        payload = packet.get("payload")

        if isinstance(payload, dict):
            found.append(payload)

    return found


def _single_packet(
    bundle: dict[str, Any],
    packet_type: str,
) -> dict[str, Any]:
    found = _packet_payloads(bundle, packet_type)

    if len(found) != 1:
        raise LegacyNormalizationError(
            f"expected exactly one {packet_type} packet; found {len(found)}"
        )

    return found[0]


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _normalize_signal_title(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(
        r"^(show|ask|tell) hn:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text).strip(" -:?")
    return _normalize_text(text)


def _policy_cluster(
    policy: dict[str, Any],
    cluster_id: str,
) -> dict[str, Any] | None:
    clusters = policy.get("clusters")

    if not isinstance(clusters, list):
        raise LegacyNormalizationError("policy clusters must be a list")

    matches = [
        cluster
        for cluster in clusters
        if isinstance(cluster, dict)
        and cluster.get("id") == cluster_id
    ]

    if len(matches) != 1:
        return None

    return matches[0]


def _matching_public_signal(
    query: str,
    search_packet: dict[str, Any],
) -> dict[str, Any] | None:
    evidence = search_packet.get("evidence")

    if not isinstance(evidence, list):
        return None

    normalized_query = _normalize_text(query)

    matches: list[dict[str, Any]] = []

    for candidate in evidence:
        if not isinstance(candidate, dict):
            continue

        source = str(candidate.get("source") or "").strip()
        url = str(candidate.get("url") or "").strip()
        observed_at = candidate.get("observed_at")

        if not source or not url or not valid_timestamp(observed_at):
            continue

        if _normalize_signal_title(candidate.get("title")) != normalized_query:
            continue

        matches.append(candidate)

    if not matches:
        return None

    matches.sort(
        key=lambda item: (
            str(item.get("source") or ""),
            str(item.get("url") or ""),
        )
    )

    return matches[0]


def _keyword_receipt(
    *,
    intake: dict[str, Any],
    search_packet: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    query = str(intake.get("query") or search_packet.get("query") or "").strip()

    if not query:
        raise LegacyNormalizationError("intake query is required")

    signal = _matching_public_signal(query, search_packet)

    if signal is not None:
        metrics = {
            key: value
            for key, value in signal.items()
            if key
            not in {
                "source",
                "title",
                "url",
                "observed_at",
                "matched_keywords",
            }
        }

        return build_keyword_receipt(
            keyword=query,
            keyword_state="LIVE_ACQUIRED_KEYWORD",
            provider=str(signal["source"]),
            acquisition_method="PUBLIC_SIGNAL_TITLE",
            retrieval_timestamp=str(signal["observed_at"]),
            market="UNSPECIFIED",
            locale="UNSPECIFIED",
            device_context=None,
            raw_source_reference=str(signal["url"]),
            provider_metrics=metrics,
            query_context=str(intake.get("topic_cluster") or ""),
        )

    captured_at = search_packet.get("captured_at")

    if not valid_timestamp(captured_at):
        raise LegacyNormalizationError(
            "derived keyword requires valid search packet capture timestamp"
        )

    return build_keyword_receipt(
        keyword=query,
        keyword_state="DERIVED_KEYWORD",
        provider=str(policy.get("schema") or "anarchi-intake-policy"),
        acquisition_method="CURATED_POLICY_QUERY",
        retrieval_timestamp=str(captured_at),
        market="UNSPECIFIED",
        locale="UNSPECIFIED",
        device_context=None,
        raw_source_reference=None,
        provider_metrics={
            "legacy_scores": search_packet.get("scores", {}),
            "measurement_disclaimer": (
                (search_packet.get("seo_plan") or {}).get(
                    "measurement_disclaimer"
                )
            ),
        },
        query_context=str(intake.get("topic_cluster") or ""),
    )


def _niche_disposition(
    *,
    intake: dict[str, Any],
    search_packet: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[str, str]:
    cluster_id = str(intake.get("topic_cluster") or "").strip()
    cluster = _policy_cluster(policy, cluster_id)

    if cluster is None:
        return (
            "AMBIGUOUS",
            "legacy intake references no unique cluster in the supplied policy",
        )

    query = _normalize_text(
        intake.get("query") or search_packet.get("query") or ""
    )

    configured_queries = {
        _normalize_text(value)
        for value in cluster.get("queries", [])
        if str(value or "").strip()
    }

    if query in configured_queries:
        return (
            "IN_NICHE",
            "query is explicitly enumerated by the versioned intake policy cluster",
        )

    keywords = [
        _normalize_text(value)
        for value in cluster.get("keywords", [])
        if str(value or "").strip()
    ]

    if any(keyword and keyword in query for keyword in keywords):
        return (
            "IN_NICHE",
            "query contains a keyword explicitly enumerated by the versioned intake policy cluster",
        )

    evidence = search_packet.get("evidence")

    if isinstance(evidence, list):
        allowed_keywords = set(keywords)

        for signal in evidence:
            if not isinstance(signal, dict):
                continue

            matched = {
                _normalize_text(value)
                for value in signal.get("matched_keywords", [])
            }

            if allowed_keywords.intersection(matched):
                return (
                    "IN_NICHE",
                    "retained public signal carries cluster-keyword overlap recorded by legacy intake",
                )

    return (
        "AMBIGUOUS",
        "legacy cluster label alone was insufficient to independently re-earn IN_NICHE",
    )


def _niche_assessment(
    *,
    intake: dict[str, Any],
    search_packet: dict[str, Any],
    policy: dict[str, Any],
    keyword_receipt: dict[str, Any],
) -> dict[str, Any]:
    disposition, rationale = _niche_disposition(
        intake=intake,
        search_packet=search_packet,
        policy=policy,
    )

    policy_schema = str(
        policy.get("schema")
        or "anarchi.editorial-intake-policy.unknown"
    )

    policy_digest = canonical_digest(policy)

    return build_niche_assessment(
        keyword_receipt,
        niche_definition_id=policy_schema,
        niche_definition_version=policy_digest,
        disposition=disposition,
        rationale=rationale,
    )


def _source_content(document: dict[str, Any]) -> str:
    page = document.get("page")

    if isinstance(page, dict):
        excerpt = str(page.get("excerpt") or "").strip()

        if excerpt:
            return excerpt

    return str(document.get("search_snippet") or "").strip()


def _source_retrieved_at(document: dict[str, Any]) -> str:
    page = document.get("page")

    if isinstance(page, dict):
        retrieved_at = page.get("retrieved_at")

        if valid_timestamp(retrieved_at):
            return str(retrieved_at)

    captured_at = document.get("captured_at")

    if valid_timestamp(captured_at):
        return str(captured_at)

    raise LegacyNormalizationError(
        "source document has no valid retrieval/capture timestamp"
    )


def _source_updated_at(document: dict[str, Any]) -> str | None:
    metrics = document.get("metrics")

    if not isinstance(metrics, dict):
        return None

    value = metrics.get("updated_at")

    if valid_timestamp(value):
        return str(value)

    return None


def _evidence_receipts(
    *,
    bundle: dict[str, Any],
    keyword_receipt: dict[str, Any],
    niche_assessment: dict[str, Any],
    query: str,
) -> list[dict[str, Any]]:
    if niche_assessment.get("disposition") != "IN_NICHE":
        raise LegacyNormalizationError(
            "evidence normalization withheld because niche is not IN_NICHE"
        )

    documents = _packet_payloads(bundle, "source_document")

    if not documents:
        raise LegacyNormalizationError(
            "at least one source_document packet is required"
        )

    receipts: list[dict[str, Any]] = []
    query_digest = canonical_digest({"query": query})

    for document in documents:
        relevance = document.get("relevance")

        if not isinstance(relevance, dict):
            continue

        if relevance.get("passed") is not True:
            continue

        source_url = str(document.get("url") or "").strip()
        source_title = str(document.get("title") or "").strip()
        provider = str(document.get("provider") or "unknown").strip()
        content = _source_content(document)

        if not source_url or not content:
            continue

        source_quality = {
            "provider": provider,
            "authoritative_domain": bool(
                relevance.get("authoritative_domain")
            ),
            "legacy_relevance_policy_version": relevance.get(
                "policy_version"
            ),
            "legacy_relevance_score": relevance.get("score"),
        }

        receipt = build_evidence_receipt(
            keyword_receipt_digest=keyword_receipt["receipt_digest"],
            query_digest=query_digest,
            source_url=source_url,
            source_title=source_title,
            source_identity=canonical_digest(
                {
                    "provider": provider,
                    "url": source_url,
                }
            ),
            retrieved_at=_source_retrieved_at(document),
            published_at=None,
            updated_at=_source_updated_at(document),
            content_digest=canonical_digest({"content": content}),
            topic_alignment="ALIGNED",
            niche_alignment="IN_NICHE",
            freshness_requirement=UNKNOWN_FRESHNESS_REQUIREMENT,
            source_quality=source_quality,
            claim_usefulness="CANDIDATE_EVIDENCE_ONLY",
        )

        receipts.append(receipt)

    if not receipts:
        raise LegacyNormalizationError(
            "no legacy source document safely normalized into evidence"
        )

    receipts.sort(
        key=lambda item: (
            item["source_url"],
            item["evidence_receipt_digest"],
        )
    )

    return receipts


def _affiliate_hints(bundle: dict[str, Any]) -> list[str]:
    hints: set[str] = set()

    for payload in _packet_payloads(bundle, "affiliate_opportunity"):
        name = str(payload.get("name") or "").strip()
        category = str(payload.get("category") or "").strip()

        if name:
            hints.add(name)

        if category:
            hints.add(category)

    return sorted(hints)


def normalize_legacy_bundle(
    source_bundle: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    if source_bundle.get("schema") != "anarchi.editorial-source-bundle.v1":
        raise LegacyNormalizationError(
            "unsupported legacy source bundle schema"
        )

    intake = source_bundle.get("intake")

    if not isinstance(intake, dict):
        raise LegacyNormalizationError("source bundle intake must be an object")

    search_packet = _single_packet(source_bundle, "search_intake")

    query = str(
        intake.get("query")
        or search_packet.get("query")
        or ""
    ).strip()

    if not query:
        raise LegacyNormalizationError("query is required")

    keyword = _keyword_receipt(
        intake=intake,
        search_packet=search_packet,
        policy=policy,
    )

    niche = _niche_assessment(
        intake=intake,
        search_packet=search_packet,
        policy=policy,
        keyword_receipt=keyword,
    )

    evidence = _evidence_receipts(
        bundle=source_bundle,
        keyword_receipt=keyword,
        niche_assessment=niche,
        query=query,
    )

    seo_legacy = search_packet.get("seo_plan")

    if not isinstance(seo_legacy, dict):
        seo_legacy = intake.get("seo_plan")

    if not isinstance(seo_legacy, dict):
        seo_legacy = {}

    supporting_queries = [
        str(value)
        for value in seo_legacy.get("secondary_keywords", [])
        if str(value or "").strip()
    ]

    unknown_freshness_count = sum(
        1
        for item in evidence
        if item.get("freshness_state") == "UNKNOWN"
    )

    known_evidence_gaps: list[str] = []

    if unknown_freshness_count:
        known_evidence_gaps.append(
            f"{unknown_freshness_count} normalized evidence source(s) lack a canonical source-age determination"
        )

    affiliate_hints = _affiliate_hints(source_bundle)

    topic = build_topic_packet(
        niche_assessment=niche,
        keyword_receipt=keyword,
        search_intent=str(
            intake.get("search_intent")
            or seo_legacy.get("intent")
            or "UNSPECIFIED"
        ),
        supporting_queries=supporting_queries,
        evidence_receipts=evidence,
        freshness_requirement="BEST_AVAILABLE",
        article_opportunity="LEGACY_READY_INTAKE_NORMALIZED_FOR_ARTICLE_CANDIDATE",
        proposed_subject=query,
        known_evidence_gaps=known_evidence_gaps,
        affiliate_hints=affiliate_hints,
        seo_inputs={
            "legacy_seo_plan": seo_legacy,
            "authority_state": "INPUT_ONLY",
        },
    )

    required_sections = [
        str(value)
        for value in seo_legacy.get("required_sections", [])
        if str(value or "").strip()
    ]

    seo_plan = build_seo_plan(
        topic_packet_digest=topic["topic_packet_digest"],
        primary_query=query,
        supporting_queries=supporting_queries,
        search_intent=topic["search_intent"],
        topic_entities=[
            str(intake.get("topic_cluster") or "")
        ],
        question_coverage=required_sections,
        content_gaps=known_evidence_gaps,
        title_direction=str(
            seo_legacy.get("title_pattern")
            or query
        ),
        heading_structure=required_sections,
        internal_link_opportunities=[],
        intent_class=str(
            intake.get("search_intent")
            or seo_legacy.get("intent")
            or "UNSPECIFIED"
        ),
    )

    article_input = build_article_input(
        topic,
        evidence_packet_digests=[
            item["evidence_receipt_digest"]
            for item in evidence
        ],
        seo_plan_digest=seo_plan["seo_plan_digest"],
        affiliate_candidate_digests=[],
        editorial_constraints=[
            "source evidence is candidate evidence only until atomic claim review",
            "legacy semantic QA may not substitute for atomic claim verification",
            "derived customer-facing language must earn its own factual disposition",
        ],
        brand_constraints=[],
    )

    payload = {
        "schema": BRIDGE_SCHEMA,
        "implementation": BRIDGE_IMPLEMENTATION,
        "legacy_bundle_digest": canonical_digest(source_bundle),
        "policy_digest": canonical_digest(policy),
        "keyword_receipt": keyword,
        "niche_assessment": niche,
        "evidence_receipts": evidence,
        "topic_packet": topic,
        "seo_plan": seo_plan,
        "article_input": article_input,
        "legacy_affiliate_hints": affiliate_hints,
        "affiliate_candidate_digests": [],
        "freshness_policy_state": "NOT_DEFINED",
        "factual_authority": "NONE",
        "publication_authority": "NONE",
        "approval": "NONE",
    }

    payload["bridge_digest"] = canonical_digest(payload)

    return payload
