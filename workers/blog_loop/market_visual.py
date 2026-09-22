"""Publication proof, telemetry, image opportunity, and visual candidate contracts.

The module deliberately has no execution adapters.  It describes payloads
that a future manually wired adapter must produce and independently verify.
"""

from __future__ import annotations

from typing import Any

from .core import (
    NO_AUTHORITY,
    assert_valid,
    canonical_digest,
    require,
    seal_receipt,
    valid_digest,
    valid_timestamp,
    valid_url,
    validate_authority_none,
    validate_receipt,
)


OPPORTUNITY_STATES = {"NO_OPPORTUNITY", "POSSIBLE_OPPORTUNITY", "STRONG_OPPORTUNITY", "INSUFFICIENT_EVIDENCE"}
IMAGE_ROLES = {"HERO", "FEATURED_THUMBNAIL", "SOCIAL_CARD", "INLINE_EXPLAINER", "COMPARISON_GRAPHIC", "PROCESS_DIAGRAM", "PRODUCT_SUPPORT", "INFOGRAPHIC_SNIPPET"}
REASON_CODES = {
    "MISSING_HERO_IMAGE", "MISSING_SOCIAL_PREVIEW", "COMPARISON_WITHOUT_VISUAL",
    "PROCESS_CONTENT_WITHOUT_DIAGRAM", "HIGH_BOUNCE_LOW_SCROLL",
    "HIGH_VALUE_POST_WITH_NO_IMAGE", "AFFILIATE_SECTION_WITHOUT_VISUAL_SUPPORT",
    "EXISTING_IMAGE_LOW_RELEVANCE", "EXISTING_IMAGE_OFF_BRAND", "EXISTING_IMAGE_STALE",
    "SOCIAL_PREVIEW_WEAK", "INSUFFICIENT_MARKET_DATA",
}


def build_publication_execution_receipt(*, article_digest: str, claim_review_digest: str,
                                        human_approval_digest: str, publication_authority_digest: str,
                                        adapter_id: str, executed_at: str, public_url: str,
                                        published_bytes_digest: str, idempotency_key: str,
                                        replay_disposition: str) -> dict[str, Any]:
    """Record an execution that happened elsewhere; never perform publication."""
    payload = {
        "schema": "anarchi.publication-execution-receipt.v1",
        "article_state": "ARTICLE_DRAFTED", "claim_state": "CLAIMS_REVIEWED",
        "human_state": "HUMAN_APPROVED", "authority_state": "PUBLICATION_AUTHORITY_PRESENT",
        "execution_state": "PUBLICATION_EXECUTED", "article_digest": article_digest,
        "claim_review_digest": claim_review_digest, "human_approval_digest": human_approval_digest,
        "publication_authority_digest": publication_authority_digest, "adapter_id": adapter_id,
        "executed_at": executed_at, "public_url": public_url,
        "published_bytes_digest": published_bytes_digest, "idempotency_key": idempotency_key,
        "replay_disposition": replay_disposition,
    }
    result = seal_receipt(payload, "publication_receipt_digest")
    assert_valid(validate_publication_receipt(result))
    return result


def validate_publication_receipt(value: dict[str, Any]) -> tuple[str, ...]:
    errors = list(validate_receipt(value, digest_field="publication_receipt_digest"))
    for field in ("article_digest", "claim_review_digest", "human_approval_digest",
                  "publication_authority_digest", "published_bytes_digest"):
        require(valid_digest(value.get(field)), f"{field} invalid", errors)
    require(valid_timestamp(value.get("executed_at")), "execution timestamp invalid", errors)
    require(valid_url(value.get("public_url")), "public URL invalid", errors)
    require(bool(value.get("adapter_id")), "adapter identity required", errors)
    require(bool(value.get("idempotency_key")), "idempotency key required", errors)
    require(value.get("replay_disposition") in {"FIRST_EXECUTION", "DUPLICATE_REPLAY_BLOCKED"}, "replay disposition invalid", errors)
    return tuple(errors)


def build_telemetry_receipt(*, post_id: str, publication_receipt_digest: str, topic_id: str,
                            niche_id: str, primary_keyword: str, published_at: str,
                            observation_window: dict[str, str], provider: str, property_id: str,
                            traffic_source: str, metrics: dict[str, Any], image_inventory: list[dict[str, Any]],
                            last_observed_at: str, retrieved_at: str, previous_receipt_digest: str | None = None) -> dict[str, Any]:
    payload = {
        "schema": "anarchi.post-telemetry.v1", "post_id": post_id,
        "publication_receipt_digest": publication_receipt_digest, "topic_id": topic_id,
        "niche_id": niche_id, "primary_keyword": primary_keyword, "published_at": published_at,
        "observation_window": observation_window, "provider": provider, "property_id": property_id,
        "traffic_source": traffic_source, "metrics": metrics,
        "image_present": bool(image_inventory), "image_inventory": image_inventory,
        "last_observed_at": last_observed_at, "retrieved_at": retrieved_at,
        "previous_receipt_digest": previous_receipt_digest,
        "append_only": True, **NO_AUTHORITY,
    }
    result = seal_receipt(payload, "telemetry_receipt_digest")
    assert_valid(validate_telemetry_receipt(result))
    return result


def validate_telemetry_receipt(value: dict[str, Any]) -> tuple[str, ...]:
    allowed_metrics = {
        "impressions", "clicks", "ctr", "pageviews", "engaged_sessions", "bounce_rate",
        "engagement_rate", "scroll_depth", "time_on_page", "affiliate_clicks",
        "conversion_events", "social_shares",
    }
    errors = list(validate_receipt(value, digest_field="telemetry_receipt_digest"))
    errors.extend(validate_authority_none(value))
    require(valid_digest(value.get("publication_receipt_digest")), "publication receipt binding invalid", errors)
    require(valid_timestamp(value.get("published_at")), "published_at invalid", errors)
    require(valid_timestamp(value.get("last_observed_at")), "last_observed_at invalid", errors)
    require(valid_timestamp(value.get("retrieved_at")), "telemetry retrieval timestamp invalid", errors)
    window = value.get("observation_window", {})
    require(valid_timestamp(window.get("start")), "observation window start invalid", errors)
    require(valid_timestamp(window.get("end")), "observation window end invalid", errors)
    require(bool(value.get("provider")) and bool(value.get("property_id")), "provider and property identity required", errors)
    metrics = value.get("metrics")
    require(isinstance(metrics, dict), "metrics must be an object", errors)
    if isinstance(metrics, dict):
        require(set(metrics).issubset(allowed_metrics), "unsupported or fabricated metric field", errors)
        require(all(metric is None or isinstance(metric, (int, float)) for metric in metrics.values()), "metric values must be numeric or unavailable", errors)
    require(value.get("append_only") is True, "telemetry must remain append-only", errors)
    require(value.get("image_present") == bool(value.get("image_inventory")), "image presence must match inventory", errors)
    return tuple(errors)


def analyze_image_opportunity(telemetry: dict[str, Any], *, article_digest: str,
                              has_comparison: bool = False, has_process: bool = False) -> dict[str, Any]:
    assert_valid(validate_telemetry_receipt(telemetry))
    metrics, reasons, roles = telemetry["metrics"], [], []
    if not metrics or len([v for v in metrics.values() if v is not None]) < 2:
        state = "INSUFFICIENT_EVIDENCE"
        reasons.append("INSUFFICIENT_MARKET_DATA")
    else:
        if not telemetry["image_present"]:
            reasons.extend(["MISSING_HERO_IMAGE", "MISSING_SOCIAL_PREVIEW"])
            roles.extend(["HERO", "SOCIAL_CARD"])
        if has_comparison:
            reasons.append("COMPARISON_WITHOUT_VISUAL")
            roles.append("COMPARISON_GRAPHIC")
        if has_process:
            reasons.append("PROCESS_CONTENT_WITHOUT_DIAGRAM")
            roles.append("PROCESS_DIAGRAM")
        low_scroll = metrics.get("scroll_depth") is not None and metrics["scroll_depth"] < 0.35
        high_bounce = metrics.get("bounce_rate") is not None and metrics["bounce_rate"] > 0.7
        if low_scroll and high_bounce:
            reasons.append("HIGH_BOUNCE_LOW_SCROLL")
        state = "POSSIBLE_OPPORTUNITY" if reasons else "NO_OPPORTUNITY"
        if len(set(reasons)) >= 4:
            state = "STRONG_OPPORTUNITY"
    payload = {
        "schema": "anarchi.image-opportunity.v1", "post_id": telemetry["post_id"],
        "publication_receipt_digest": telemetry["publication_receipt_digest"],
        "telemetry_receipt_digests": [telemetry["telemetry_receipt_digest"]],
        "article_digest": article_digest, "opportunity_state": state,
        "reason_codes": sorted(set(reasons)), "recommended_image_roles": sorted(set(roles)),
        "expected_goal": "IMPROVE_REPRESENTATION_WITHOUT_INCREASING_EPISTEMIC_STRENGTH",
        "evidence_basis": {"observed_metric_names": sorted(metrics), "causality": "NOT_CAUSALLY_ESTABLISHED"},
        "recommendation_only": True, **NO_AUTHORITY,
    }
    return seal_receipt(payload, "assessment_digest")


def validate_image_opportunity(value: dict[str, Any]) -> tuple[str, ...]:
    errors = list(validate_receipt(value, digest_field="assessment_digest"))
    errors.extend(validate_authority_none(value))
    require(value.get("opportunity_state") in OPPORTUNITY_STATES, "opportunity state invalid", errors)
    require(set(value.get("reason_codes", [])).issubset(REASON_CODES), "image reason code invalid", errors)
    require(set(value.get("recommended_image_roles", [])).issubset(IMAGE_ROLES), "image role invalid", errors)
    require(value.get("recommendation_only") is True, "opportunity must remain recommendation-only", errors)
    require(value.get("evidence_basis", {}).get("causality") == "NOT_CAUSALLY_ESTABLISHED", "causality claim forbidden", errors)
    return tuple(errors)


def build_image_request(*, mode: str, post_id: str, section_id: str | None, topic_id: str,
                        niche_id: str, image_role: str, target_intent: str, reader_problem: str,
                        seo_context: dict[str, Any], brand_profile: dict[str, Any],
                        truth_constraints: list[str], affiliate_constraints: list[str],
                        evidence_packet_references: list[str], market_opportunity_references: list[str],
                        request_reason: str) -> dict[str, Any]:
    if mode not in {"PULL_MODE", "PUSH_MODE"}:
        raise ValueError("image request mode invalid")
    payload = {
        "schema": "anarchi.blog-image-request.v1", "request_mode": mode,
        "post_id": post_id, "section_id": section_id, "topic_id": topic_id, "niche_id": niche_id,
        "image_role": image_role, "target_intent": target_intent, "reader_problem": reader_problem,
        "seo_context": seo_context, "brand_profile": brand_profile,
        "truth_constraints": truth_constraints, "affiliate_constraints": affiliate_constraints,
        "evidence_packet_references": evidence_packet_references,
        "market_opportunity_references": market_opportunity_references,
        "request_reason": request_reason, "generation_authority": "NONE", **NO_AUTHORITY,
    }
    payload["request_id"] = "image_request_" + canonical_digest(payload)[:24]
    result = seal_receipt(payload, "request_digest")
    assert_valid(validate_image_request(result))
    return result


def validate_image_request(value: dict[str, Any]) -> tuple[str, ...]:
    errors = list(validate_receipt(value, digest_field="request_digest"))
    errors.extend(validate_authority_none(value))
    require(value.get("request_mode") in {"PULL_MODE", "PUSH_MODE"}, "request mode invalid", errors)
    require(value.get("image_role") in IMAGE_ROLES, "image role invalid", errors)
    require(value.get("generation_authority") == "NONE", "image request cannot authorize generation", errors)
    require(bool(value.get("request_reason")), "request reason required", errors)
    require(bool(value.get("truth_constraints")), "truth constraints required", errors)
    return tuple(errors)


def build_image_plan(request: dict[str, Any], *, required_semantic_elements: list[str],
                     forbidden_semantic_elements: list[str], composition_guidance: list[str],
                     text_on_image_policy: str, product_restrictions: list[str],
                     factual_restrictions: list[str], aspect_roles: list[str], generation_strategy: str) -> dict[str, Any]:
    assert_valid(validate_image_request(request))
    payload = {
        "schema": "anarchi.blog-image-plan.v1", "request_digest": request["request_digest"],
        "image_role": request["image_role"], "topic_id": request["topic_id"],
        "section_id": request["section_id"], "reader_intent": request["target_intent"],
        "required_semantic_elements": required_semantic_elements,
        "forbidden_semantic_elements": forbidden_semantic_elements,
        "brand_constraints": request["brand_profile"], "composition_guidance": composition_guidance,
        "text_on_image_policy": text_on_image_policy, "product_restrictions": product_restrictions,
        "factual_restrictions": factual_restrictions, "aspect_roles": aspect_roles,
        "generation_strategy": generation_strategy, "execution_authority": "NONE", **NO_AUTHORITY,
    }
    result = seal_receipt(payload, "plan_digest")
    assert_valid(validate_image_plan(result))
    return result


def validate_image_plan(value: dict[str, Any]) -> tuple[str, ...]:
    errors = list(validate_receipt(value, digest_field="plan_digest"))
    errors.extend(validate_authority_none(value))
    require(valid_digest(value.get("request_digest")), "request binding invalid", errors)
    require(value.get("image_role") in IMAGE_ROLES, "image role invalid", errors)
    require(value.get("execution_authority") == "NONE", "image plan cannot authorize execution", errors)
    require(isinstance(value.get("forbidden_semantic_elements"), list), "forbidden elements required", errors)
    require(isinstance(value.get("factual_restrictions"), list) and bool(value.get("factual_restrictions")), "factual restrictions required", errors)
    return tuple(errors)


def build_image_candidate(*, request_digest: str, plan_digest: str, provider_id: str,
                          model_id: str, runtime_id: str, generation_configuration: dict[str, Any],
                          asset_reference: str, asset_sha256: str, dimensions: dict[str, int],
                          materialization_state: str) -> dict[str, Any]:
    payload = {
        "schema": "anarchi.blog-image-candidate.v1", "request_digest": request_digest,
        "plan_digest": plan_digest, "provider_id": provider_id, "model_id": model_id,
        "runtime_id": runtime_id, "generation_configuration": generation_configuration,
        "asset_reference": asset_reference, "asset_sha256": asset_sha256,
        "dimensions": dimensions, "materialization_state": materialization_state,
        "candidate_identity": canonical_digest({"request": request_digest, "plan": plan_digest,
                                                   "asset": asset_sha256, "runtime": runtime_id}),
        **NO_AUTHORITY,
    }
    result = seal_receipt(payload, "generation_receipt_digest")
    assert_valid(validate_image_candidate(result))
    return result


def validate_image_candidate(value: dict[str, Any]) -> tuple[str, ...]:
    errors = list(validate_receipt(value, digest_field="generation_receipt_digest"))
    errors.extend(validate_authority_none(value))
    for field in ("request_digest", "plan_digest", "asset_sha256", "candidate_identity"):
        require(valid_digest(value.get(field)), f"{field} invalid", errors)
    require(all(bool(value.get(field)) for field in ("provider_id", "model_id", "runtime_id")), "execution identities required", errors)
    dimensions = value.get("dimensions", {})
    require(isinstance(dimensions.get("width"), int) and dimensions.get("width", 0) > 0, "image width invalid", errors)
    require(isinstance(dimensions.get("height"), int) and dimensions.get("height", 0) > 0, "image height invalid", errors)
    require(value.get("materialization_state") in {"MATERIALIZED_CANDIDATE", "FAILED"}, "materialization state invalid", errors)
    return tuple(errors)


def build_image_review_interface(*, candidate_digest: str, automated_findings: list[dict[str, Any]],
                                 human_review_state: str) -> dict[str, Any]:
    payload = {
        "schema": "anarchi.blog-image-review-interface.v1", "candidate_digest": candidate_digest,
        "automated_findings": automated_findings, "r16_applicability": "DEFERRED",
        "automated_positive_authority": "WITHHELD", "human_review_state": human_review_state,
        **NO_AUTHORITY,
    }
    return seal_receipt(payload, "review_interface_digest")


def build_before_after_comparison(*, post_id: str, url_identity: str, image_deployment_receipt: str,
                                  pre_image_telemetry: str, post_image_telemetry: str,
                                  comparison_window: dict[str, str], traffic_source: str,
                                  observed_changes: dict[str, Any], confounder_notes: list[str]) -> dict[str, Any]:
    payload = {
        "schema": "anarchi.image-market-comparison.v1", "post_id": post_id,
        "url_identity": url_identity, "image_deployment_receipt": image_deployment_receipt,
        "pre_image_window_receipt": pre_image_telemetry, "post_image_window_receipt": post_image_telemetry,
        "comparison_window": comparison_window, "traffic_source": traffic_source,
        "observed_changes": observed_changes, "interpretation": "OBSERVED_CHANGE",
        "relationship": "ASSOCIATION", "causality": "NOT_CAUSALLY_ESTABLISHED",
        "confounder_notes": confounder_notes, **NO_AUTHORITY,
    }
    return seal_receipt(payload, "comparison_digest")


def validate_before_after_comparison(value: dict[str, Any]) -> tuple[str, ...]:
    errors = list(validate_receipt(value, digest_field="comparison_digest"))
    errors.extend(validate_authority_none(value))
    require(value.get("interpretation") == "OBSERVED_CHANGE", "comparison interpretation invalid", errors)
    require(value.get("relationship") == "ASSOCIATION", "comparison relationship invalid", errors)
    require(value.get("causality") == "NOT_CAUSALLY_ESTABLISHED", "causality must not be claimed", errors)
    for field in ("image_deployment_receipt", "pre_image_window_receipt", "post_image_window_receipt"):
        require(valid_digest(value.get(field)), f"{field} invalid", errors)
    return tuple(errors)
