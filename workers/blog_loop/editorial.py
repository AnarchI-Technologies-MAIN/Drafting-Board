"""Demand, niche, evidence, topic, affiliate, and SEO contracts.

These transformations establish provenance and bounded eligibility only.
They never establish factual truth, approval, CTA authority, or publication
authority.
"""

from __future__ import annotations

from typing import Any

from .core import (
    NO_AUTHORITY,
    assert_valid,
    canonical_digest,
    exact_fields,
    require,
    seal_receipt,
    valid_digest,
    valid_timestamp,
    valid_url,
    validate_authority_none,
    validate_receipt,
)


KEYWORD_STATES = {"LIVE_ACQUIRED_KEYWORD", "DERIVED_KEYWORD", "MODEL_SUGGESTED_KEYWORD", "HISTORICAL_KEYWORD"}
NICHE_STATES = {"IN_NICHE", "ADJACENT", "OUT_OF_NICHE", "AMBIGUOUS"}
FRESHNESS_STATES = {"CURRENT", "STALE", "UNKNOWN"}


def build_keyword_receipt(**values: Any) -> dict[str, Any]:
    payload = {
        "schema": "anarchi.keyword-observation.v1",
        "keyword": values["keyword"],
        "keyword_state": values["keyword_state"],
        "provider": values["provider"],
        "acquisition_method": values["acquisition_method"],
        "retrieval_timestamp": values["retrieval_timestamp"],
        "market": values["market"],
        "locale": values["locale"],
        "device_context": values.get("device_context"),
        "raw_source_reference": values.get("raw_source_reference"),
        "provider_metrics": values.get("provider_metrics", {}),
        "query_context": values.get("query_context", ""),
        **NO_AUTHORITY,
    }
    receipt = seal_receipt(payload)
    assert_valid(validate_keyword_receipt(receipt))
    return receipt


def validate_keyword_receipt(value: dict[str, Any]) -> tuple[str, ...]:
    required = {
        "schema", "keyword", "keyword_state", "provider", "acquisition_method",
        "retrieval_timestamp", "market", "locale", "device_context",
        "raw_source_reference", "provider_metrics", "query_context",
        "factual_authority", "publication_authority", "approval", "receipt_digest",
    }
    errors = exact_fields(value, required)
    errors.extend(validate_receipt(value))
    errors.extend(validate_authority_none(value))
    require(value.get("schema") == "anarchi.keyword-observation.v1", "keyword schema mismatch", errors)
    require(isinstance(value.get("keyword"), str) and bool(value.get("keyword", "").strip()), "keyword required", errors)
    require(value.get("keyword_state") in KEYWORD_STATES, "keyword state invalid", errors)
    require(isinstance(value.get("provider"), str) and bool(value.get("provider", "").strip()), "provider required", errors)
    require(valid_timestamp(value.get("retrieval_timestamp")), "retrieval timestamp invalid", errors)
    require(isinstance(value.get("provider_metrics"), dict), "provider metrics must be an object", errors)
    if value.get("keyword_state") == "LIVE_ACQUIRED_KEYWORD":
        require(value.get("acquisition_method") not in {"MODEL", "DERIVATION", ""}, "live keyword cannot use generated acquisition", errors)
        require(bool(value.get("raw_source_reference")), "live keyword requires raw source reference", errors)
    return tuple(errors)


def build_niche_assessment(keyword_receipt: dict[str, Any], *, niche_definition_id: str,
                           niche_definition_version: str, disposition: str, rationale: str) -> dict[str, Any]:
    assert_valid(validate_keyword_receipt(keyword_receipt))
    payload = {
        "schema": "anarchi.niche-assessment.v1",
        "keyword_receipt_digest": keyword_receipt["receipt_digest"],
        "niche_definition_id": niche_definition_id,
        "niche_definition_version": niche_definition_version,
        "disposition": disposition,
        "rationale": rationale,
        **NO_AUTHORITY,
    }
    result = seal_receipt(payload, "assessment_digest")
    assert_valid(validate_niche_assessment(result))
    return result


def validate_niche_assessment(value: dict[str, Any]) -> tuple[str, ...]:
    errors = list(validate_receipt(value, digest_field="assessment_digest"))
    errors.extend(validate_authority_none(value))
    require(valid_digest(value.get("keyword_receipt_digest")), "keyword receipt binding invalid", errors)
    require(value.get("disposition") in NICHE_STATES, "niche disposition invalid", errors)
    require(bool(value.get("niche_definition_id")), "niche definition id required", errors)
    require(bool(value.get("niche_definition_version")), "niche definition version required", errors)
    require(bool(value.get("rationale")), "niche rationale required", errors)
    return tuple(errors)


def derive_freshness(*, retrieved_at: str, published_at: str | None,
                     updated_at: str | None, freshness_requirement: dict[str, Any]) -> str:
    if not valid_timestamp(retrieved_at):
        raise ValueError("retrieved_at invalid")
    source_time = updated_at or published_at
    if source_time is None or not valid_timestamp(source_time):
        return "UNKNOWN"
    max_age_days = freshness_requirement.get("max_age_days")
    if not isinstance(max_age_days, int) or max_age_days < 0:
        return "UNKNOWN"
    from datetime import datetime
    retrieved = datetime.fromisoformat(retrieved_at[:-1] + "+00:00")
    source = datetime.fromisoformat(source_time[:-1] + "+00:00")
    return "CURRENT" if (retrieved - source).days <= max_age_days else "STALE"


def build_evidence_receipt(*, keyword_receipt_digest: str, query_digest: str, source_url: str,
                           source_title: str, source_identity: str, retrieved_at: str,
                           published_at: str | None, updated_at: str | None,
                           content_digest: str, topic_alignment: str, niche_alignment: str,
                           freshness_requirement: dict[str, Any], source_quality: dict[str, Any],
                           claim_usefulness: str) -> dict[str, Any]:
    freshness = derive_freshness(retrieved_at=retrieved_at, published_at=published_at,
                                 updated_at=updated_at, freshness_requirement=freshness_requirement)
    payload = {
        "schema": "anarchi.serp-evidence.v1",
        "keyword_receipt_digest": keyword_receipt_digest,
        "query_digest": query_digest,
        "source_url": source_url,
        "source_title": source_title,
        "source_identity": source_identity,
        "retrieved_at": retrieved_at,
        "source_published_at": published_at,
        "source_updated_at": updated_at,
        "content_digest": content_digest,
        "topic_alignment": topic_alignment,
        "niche_alignment": niche_alignment,
        "freshness_requirement": freshness_requirement,
        "freshness_state": freshness,
        "source_quality": source_quality,
        "claim_usefulness": claim_usefulness,
        **NO_AUTHORITY,
    }
    result = seal_receipt(payload, "evidence_receipt_digest")
    assert_valid(validate_evidence_receipt(result))
    return result


def validate_evidence_receipt(value: dict[str, Any]) -> tuple[str, ...]:
    errors = list(validate_receipt(value, digest_field="evidence_receipt_digest"))
    errors.extend(validate_authority_none(value))
    for field in ("keyword_receipt_digest", "query_digest", "content_digest"):
        require(valid_digest(value.get(field)), f"{field} invalid", errors)
    require(valid_url(value.get("source_url")), "source URL invalid", errors)
    require(valid_timestamp(value.get("retrieved_at")), "retrieved_at invalid", errors)
    require(value.get("freshness_state") in FRESHNESS_STATES, "freshness state invalid", errors)
    if valid_timestamp(value.get("retrieved_at")):
        expected = derive_freshness(
            retrieved_at=value["retrieved_at"], published_at=value.get("source_published_at"),
            updated_at=value.get("source_updated_at"), freshness_requirement=value.get("freshness_requirement", {}),
        )
        require(value.get("freshness_state") == expected, "freshness state not re-earned from timestamps", errors)
    require(value.get("topic_alignment") in {"ALIGNED", "MISALIGNED", "AMBIGUOUS"}, "topic alignment invalid", errors)
    require(value.get("niche_alignment") in NICHE_STATES, "niche alignment invalid", errors)
    return tuple(errors)


def build_topic_packet(*, niche_assessment: dict[str, Any], keyword_receipt: dict[str, Any],
                       search_intent: str, supporting_queries: list[str], evidence_receipts: list[dict[str, Any]],
                       freshness_requirement: str, article_opportunity: str, proposed_subject: str,
                       known_evidence_gaps: list[str], affiliate_hints: list[str], seo_inputs: dict[str, Any]) -> dict[str, Any]:
    assert_valid(validate_keyword_receipt(keyword_receipt))
    assert_valid(validate_niche_assessment(niche_assessment))
    for evidence in evidence_receipts:
        assert_valid(validate_evidence_receipt(evidence))
    payload = {
        "schema": "anarchi.topic-qualification.v1",
        "niche_assessment_digest": niche_assessment["assessment_digest"],
        "primary_keyword": keyword_receipt["keyword"],
        "keyword_receipt_digest": keyword_receipt["receipt_digest"],
        "keyword_state": keyword_receipt["keyword_state"],
        "search_intent": search_intent,
        "supporting_queries": supporting_queries,
        "evidence_receipt_digests": [e["evidence_receipt_digest"] for e in evidence_receipts],
        "freshness_requirement": freshness_requirement,
        "freshness_findings": [e["freshness_state"] for e in evidence_receipts],
        "article_opportunity": article_opportunity,
        "proposed_subject": proposed_subject,
        "known_evidence_gaps": known_evidence_gaps,
        "affiliate_opportunity_hints": affiliate_hints,
        "seo_planning_inputs": seo_inputs,
        "qualification_state": "QUALIFIED_CANDIDATE",
        **NO_AUTHORITY,
    }
    packet = seal_receipt(payload, "topic_packet_digest")
    errors = validate_topic_packet(packet, niche_assessment=niche_assessment, keyword_receipt=keyword_receipt,
                                   evidence_receipts=evidence_receipts)
    assert_valid(errors)
    return packet


def validate_topic_packet(value: dict[str, Any], *, niche_assessment: dict[str, Any],
                          keyword_receipt: dict[str, Any], evidence_receipts: list[dict[str, Any]]) -> tuple[str, ...]:
    errors = list(validate_receipt(value, digest_field="topic_packet_digest"))
    errors.extend(validate_authority_none(value))
    require(niche_assessment.get("disposition") == "IN_NICHE", "topic requires IN_NICHE assessment", errors)
    require(value.get("niche_assessment_digest") == niche_assessment.get("assessment_digest"), "niche binding mismatch", errors)
    require(value.get("keyword_receipt_digest") == keyword_receipt.get("receipt_digest"), "keyword binding mismatch", errors)
    require(bool(evidence_receipts), "topic requires evidence coverage", errors)
    require(all(not validate_evidence_receipt(item) for item in evidence_receipts), "invalid evidence receipt", errors)
    require(all(item.get("topic_alignment") == "ALIGNED" for item in evidence_receipts), "topic evidence is not aligned", errors)
    require(all(item.get("niche_alignment") == "IN_NICHE" for item in evidence_receipts), "evidence niche drift", errors)
    if value.get("freshness_requirement") == "CURRENT_REQUIRED":
        require(all(item.get("freshness_state") == "CURRENT" for item in evidence_receipts), "current evidence requirement unmet", errors)
    return tuple(errors)


def build_article_input(topic_packet: dict[str, Any], *, evidence_packet_digests: list[str],
                        seo_plan_digest: str | None, affiliate_candidate_digests: list[str],
                        editorial_constraints: list[str], brand_constraints: list[str]) -> dict[str, Any]:
    payload = {
        "schema": "anarchi.article-worker-input.v1",
        "topic_packet_digest": topic_packet["topic_packet_digest"],
        "evidence_packet_digests": evidence_packet_digests,
        "seo_plan_digest": seo_plan_digest,
        "affiliate_candidate_digests": affiliate_candidate_digests,
        "editorial_constraints": editorial_constraints,
        "brand_constraints": brand_constraints,
        "output_state": "ARTICLE_CANDIDATE_ONLY",
        **NO_AUTHORITY,
    }
    return seal_receipt(payload, "article_input_digest")


def build_affiliate_candidate(*, product_id: str, article_digest: str, niche_disposition: str,
                              article_disposition: str, purchase_intent_alignment: str,
                              availability_state: str, destination: str, destination_validity: str,
                              price_state: str, observed_price: Any, retrieval_timestamp: str,
                              affiliate_source: str, product_identity: str) -> dict[str, Any]:
    payload = {
        "schema": "anarchi.affiliate-candidate.v1", "product_id": product_id,
        "article_digest": article_digest, "niche_relevance": niche_disposition,
        "article_relevance": article_disposition, "purchase_intent_alignment": purchase_intent_alignment,
        "availability_state": availability_state, "affiliate_destination": destination,
        "destination_validity": destination_validity, "price_state": price_state,
        "observed_price": observed_price, "retrieval_timestamp": retrieval_timestamp,
        "affiliate_source": affiliate_source, "product_identity": product_identity,
        "cta_authority": "NONE", **NO_AUTHORITY,
    }
    result = seal_receipt(payload, "candidate_digest")
    assert_valid(validate_affiliate_candidate(result))
    return result


def validate_affiliate_candidate(value: dict[str, Any]) -> tuple[str, ...]:
    errors = list(validate_receipt(value, digest_field="candidate_digest"))
    errors.extend(validate_authority_none(value))
    require(value.get("cta_authority") == "NONE", "CTA authority forbidden", errors)
    require(valid_timestamp(value.get("retrieval_timestamp")), "affiliate retrieval timestamp invalid", errors)
    require(valid_url(value.get("affiliate_destination")), "affiliate destination invalid", errors)
    require(value.get("destination_validity") in {"VALID", "INVALID", "UNKNOWN"}, "destination validity invalid", errors)
    require(value.get("niche_relevance") in NICHE_STATES, "affiliate niche relevance invalid", errors)
    require(value.get("article_relevance") in {"RELEVANT", "IRRELEVANT", "AMBIGUOUS"}, "article relevance invalid", errors)
    if value.get("price_state") != "OBSERVED":
        require(value.get("observed_price") is None, "unobserved price must remain unavailable", errors)
    return tuple(errors)


def affiliate_eligible(value: dict[str, Any]) -> bool:
    return not validate_affiliate_candidate(value) and all((
        value["niche_relevance"] == "IN_NICHE", value["article_relevance"] == "RELEVANT",
        value["availability_state"] == "AVAILABLE", value["destination_validity"] == "VALID",
    ))


def build_affiliate_program_observation(*, candidate_digest: str, provider: str,
                                        program_url: str, retrieved_at: str,
                                        commission_model: str | None,
                                        commission_value: Any,
                                        cookie_duration_days: int | None,
                                        epc: float | None, conversion_rate: float | None,
                                        refund_rate: float | None, payout_terms: str | None,
                                        raw_terms_digest: str) -> dict[str, Any]:
    """Bind only program terms actually observed from a provider or terms page."""
    payload = {
        "schema": "anarchi.affiliate-program-observation.v1",
        "candidate_digest": candidate_digest, "provider": provider,
        "program_url": program_url, "retrieved_at": retrieved_at,
        "commission_model": commission_model, "commission_value": commission_value,
        "cookie_duration_days": cookie_duration_days, "epc": epc,
        "conversion_rate": conversion_rate, "refund_rate": refund_rate,
        "payout_terms": payout_terms, "raw_terms_digest": raw_terms_digest,
        "performance_authority": "OBSERVED_ONLY", "cta_authority": "NONE",
        **NO_AUTHORITY,
    }
    result = seal_receipt(payload, "program_observation_digest")
    assert_valid(validate_affiliate_program_observation(result))
    return result


def validate_affiliate_program_observation(value: dict[str, Any]) -> tuple[str, ...]:
    errors = list(validate_receipt(value, digest_field="program_observation_digest"))
    errors.extend(validate_authority_none(value))
    require(valid_digest(value.get("candidate_digest")), "candidate binding invalid", errors)
    require(valid_digest(value.get("raw_terms_digest")), "raw terms identity invalid", errors)
    require(valid_url(value.get("program_url")), "program URL invalid", errors)
    require(valid_timestamp(value.get("retrieved_at")), "program retrieval timestamp invalid", errors)
    require(bool(value.get("provider")), "program provider required", errors)
    require(value.get("performance_authority") == "OBSERVED_ONLY", "performance must remain observed-only", errors)
    require(value.get("cta_authority") == "NONE", "program terms cannot create CTA authority", errors)
    for field in ("epc", "conversion_rate", "refund_rate"):
        metric = value.get(field)
        require(metric is None or isinstance(metric, (int, float)), f"{field} must be numeric or unavailable", errors)
    for field in ("conversion_rate", "refund_rate"):
        metric = value.get(field)
        require(metric is None or 0 <= metric <= 1, f"{field} must be a 0..1 ratio", errors)
    return tuple(errors)


def rank_affiliate_candidates(items: list[tuple[dict[str, Any], dict[str, Any] | None]]) -> list[dict[str, Any]]:
    """Deterministically rank eligible candidates without inventing economics.

    Observed EPC is adjusted by an observed refund rate when both exist. Unknown
    economics remain UNKNOWN and sort below observed economics, never as zero.
    The result is still recommendation-only and cannot construct a CTA.
    """
    ranked: list[dict[str, Any]] = []
    for candidate, observation in items:
        eligible = affiliate_eligible(candidate)
        net_epc = None
        observation_digest = None
        if observation is not None:
            assert_valid(validate_affiliate_program_observation(observation))
            if observation["candidate_digest"] != candidate["candidate_digest"]:
                raise ValueError("affiliate program observation ancestry mismatch")
            observation_digest = observation["program_observation_digest"]
            if observation["epc"] is not None:
                refund = observation["refund_rate"]
                net_epc = round(observation["epc"] * (1 - refund), 6) if refund is not None else observation["epc"]
        ranked.append({
            "candidate_digest": candidate["candidate_digest"], "eligible": eligible,
            "program_observation_digest": observation_digest,
            "net_epc_state": "OBSERVED_OR_DERIVED_FROM_OBSERVED" if net_epc is not None else "UNKNOWN",
            "net_epc": net_epc, "recommendation_only": True, "cta_authority": "NONE",
        })
    ranked.sort(key=lambda item: (
        item["eligible"], item["net_epc"] is not None,
        item["net_epc"] if item["net_epc"] is not None else -1,
        item["candidate_digest"],
    ), reverse=True)
    for position, item in enumerate(ranked, 1):
        item["rank"] = position
        item["ranking_digest"] = canonical_digest({k: v for k, v in item.items() if k != "ranking_digest"})
    return ranked


def build_seo_plan(*, topic_packet_digest: str, primary_query: str, supporting_queries: list[str],
                   search_intent: str, topic_entities: list[str], question_coverage: list[str],
                   content_gaps: list[str], title_direction: str, heading_structure: list[str],
                   internal_link_opportunities: list[str], intent_class: str) -> dict[str, Any]:
    payload = {
        "schema": "anarchi.seo-plan.v1", "topic_packet_digest": topic_packet_digest,
        "primary_query": primary_query, "supporting_queries": supporting_queries,
        "search_intent": search_intent, "topic_entities": topic_entities,
        "question_coverage": question_coverage, "potential_content_gaps": content_gaps,
        "title_direction": title_direction, "heading_structure": heading_structure,
        "internal_link_opportunities": internal_link_opportunities, "intent_class": intent_class,
        "evidence_authority": "NONE", **NO_AUTHORITY,
    }
    return seal_receipt(payload, "seo_plan_digest")


def build_seo_validation(*, seo_plan_digest: str, article_digest: str, checks: dict[str, Any]) -> dict[str, Any]:
    allowed = {"title", "slug", "meta_description", "h1", "heading_structure", "query_coverage",
               "topic_coverage", "internal_links", "outbound_evidence_links", "image_alt_text",
               "canonical_url", "structured_data", "affiliate_disclosure"}
    if not set(checks).issubset(allowed):
        raise ValueError("unknown SEO validation check")
    payload = {
        "schema": "anarchi.seo-validation.v1", "seo_plan_digest": seo_plan_digest,
        "article_digest": article_digest, "checks": checks,
        "validation_state": "CANDIDATE_REVIEW", "evidence_authority": "NONE", **NO_AUTHORITY,
    }
    return seal_receipt(payload, "seo_validation_digest")
