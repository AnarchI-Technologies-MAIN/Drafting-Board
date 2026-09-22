"""Claim-bound semantic package for Illustration Lab ingress.

The visual handoff establishes identity and representation intent.

This package adds the minimum reviewed semantic context needed by the
Illustration Lab to understand and later validate the requested visual.

It does not grant:
- evidentiary authority,
- model authority,
- human approval,
- publication authority.

Bound claims are projections of an already-reviewed artifact.
They are not independent evidence.
"""

from __future__ import annotations

from typing import Any

from editorial_review_artifact import (
    ReviewedArticleArtifact,
)
from editorial_visual_request import (
    EditorialVisualRequest,
    validate_request,
)
from editorial_visual_transport import (
    build_handoff,
    to_transport_digest,
    transport_digest,
    validate_handoff,
)


EDITORIAL_VISUAL_PACKAGE_VERSION = (
    "anarchi.editorial-visual-package.v1"
)


def _bound_claim_projection(
    artifact: ReviewedArticleArtifact,
    claim_id: str,
) -> dict[str, Any]:
    claims = [
        claim
        for claim in artifact.claim_ledger.claims
        if claim.claim_id == claim_id
    ]

    if len(claims) != 1:
        raise ValueError(
            "bound claim identity does not resolve exactly once: "
            + claim_id
        )

    verifications = [
        verification
        for verification
        in artifact.article_verification.claims
        if verification.claim_id == claim_id
    ]

    if len(verifications) != 1:
        raise ValueError(
            "bound verification identity does not resolve "
            "exactly once: "
            + claim_id
        )

    claim = claims[0]
    verification = verifications[0]

    return {
        "claim_id": claim.claim_id,
        "claim_text": claim.text,
        "claim_type": claim.claim_type.value,
        "material": claim.material,
        "source_span_start": claim.source_span_start,
        "source_span_end": claim.source_span_end,
        "verification": {
            "verdict": verification.verdict.value,
            "calibration": verification.calibration.value,
            "temporal_sensitivity": (
                verification.temporal_sensitivity.value
            ),
            "acceptable": verification.acceptable,
            "relied_on_evidence": [
                {
                    "packet_id": evidence.packet_id,
                    "source_url": evidence.source_url,
                    "excerpt_digest": (
                        evidence.excerpt_digest
                    ),
                }
                for evidence in verification.evidence
            ],
        },
    }


def package_payload(
    *,
    artifact: ReviewedArticleArtifact,
    request: EditorialVisualRequest,
) -> dict[str, Any]:
    handoff = build_handoff(
        request,
        artifact,
    )

    claims = [
        _bound_claim_projection(
            artifact,
            claim_id,
        )
        for claim_id in request.bound_claim_ids
    ]

    return {
        "schema": (
            EDITORIAL_VISUAL_PACKAGE_VERSION
        ),
        "handoff": handoff,
        "reviewed_context": {
            "reviewed_article_schema": (
                artifact.schema_version
            ),
            "artifact_digest": (
                to_transport_digest(
                    artifact.artifact_digest
                )
            ),
            "article_digest": (
                to_transport_digest(
                    artifact.article_digest
                )
            ),
            "article_text": (
                artifact.article_text
            ),
            "bound_claims": claims,
        },
        "authority_state": (
            "TRANSPORT_ONLY"
        ),
        "evidentiary_authority": (
            "NONE"
        ),
        "human_approval": (
            "NONE"
        ),
        "publication_authority": (
            "NONE"
        ),
    }


def build_package(
    *,
    artifact: ReviewedArticleArtifact,
    request: EditorialVisualRequest,
) -> dict[str, Any]:
    request_errors = validate_request(
        request,
        artifact,
    )

    if request_errors:
        raise ValueError(
            "invalid editorial visual request: "
            + "; ".join(
                request_errors
            )
        )

    payload = package_payload(
        artifact=artifact,
        request=request,
    )

    result = dict(
        payload
    )

    result[
        "package_digest"
    ] = transport_digest(
        payload
    )

    errors = validate_package(
        result,
        artifact=artifact,
        request=request,
    )

    if errors:
        raise ValueError(
            "; ".join(
                errors
            )
        )

    return result


def validate_package(
    package: Any,
    *,
    artifact: ReviewedArticleArtifact,
    request: EditorialVisualRequest,
) -> tuple[str, ...]:
    errors: list[str] = []

    request_errors = validate_request(
        request,
        artifact,
    )

    if request_errors:
        errors.append(
            "source editorial visual request invalid"
        )

    if not isinstance(
        package,
        dict,
    ):
        return (
            "editorial visual package must be an object",
        )

    expected_fields = {
        "schema",
        "handoff",
        "reviewed_context",
        "authority_state",
        "evidentiary_authority",
        "human_approval",
        "publication_authority",
        "package_digest",
    }

    if set(package) != expected_fields:
        return (
            "editorial visual package fields invalid",
        )

    if (
        package["schema"]
        != EDITORIAL_VISUAL_PACKAGE_VERSION
    ):
        errors.append(
            "editorial visual package schema mismatch"
        )

    handoff = package[
        "handoff"
    ]

    handoff_errors = validate_handoff(
        handoff,
        request,
        artifact,
    )

    if handoff_errors:
        errors.append(
            "editorial visual handoff invalid"
        )

    expected_handoff = build_handoff(
        request,
        artifact,
    )

    if handoff != expected_handoff:
        errors.append(
            "editorial visual handoff changed in package"
        )

    reviewed = package[
        "reviewed_context"
    ]

    expected_reviewed_fields = {
        "reviewed_article_schema",
        "artifact_digest",
        "article_digest",
        "article_text",
        "bound_claims",
    }

    if (
        not isinstance(
            reviewed,
            dict,
        )
        or set(
            reviewed
        )
        != expected_reviewed_fields
    ):
        errors.append(
            "reviewed context fields invalid"
        )

        return tuple(
            errors
        )

    if (
        reviewed[
            "reviewed_article_schema"
        ]
        != artifact.schema_version
    ):
        errors.append(
            "reviewed article schema changed in package"
        )

    if (
        reviewed[
            "artifact_digest"
        ]
        != to_transport_digest(
            artifact.artifact_digest
        )
    ):
        errors.append(
            "reviewed artifact identity changed in package"
        )

    if (
        reviewed[
            "article_digest"
        ]
        != to_transport_digest(
            artifact.article_digest
        )
    ):
        errors.append(
            "reviewed article identity changed in package"
        )

    if (
        reviewed[
            "article_text"
        ]
        != artifact.article_text
    ):
        errors.append(
            "reviewed article text changed in package"
        )

    expected_claims = [
        _bound_claim_projection(
            artifact,
            claim_id,
        )
        for claim_id in request.bound_claim_ids
    ]

    if (
        reviewed[
            "bound_claims"
        ]
        != expected_claims
    ):
        errors.append(
            "bound reviewed claim projection changed"
        )

    projected_ids = [
        item[
            "claim_id"
        ]
        for item in reviewed[
            "bound_claims"
        ]
    ]

    if projected_ids != list(
        request.bound_claim_ids
    ):
        errors.append(
            "projected claim identities do not match request"
        )

    if (
        package[
            "authority_state"
        ]
        != "TRANSPORT_ONLY"
    ):
        errors.append(
            "package authority state invalid"
        )

    if (
        package[
            "evidentiary_authority"
        ]
        != "NONE"
    ):
        errors.append(
            "package may not carry evidentiary authority"
        )

    if (
        package[
            "human_approval"
        ]
        != "NONE"
    ):
        errors.append(
            "package may not carry human approval"
        )

    if (
        package[
            "publication_authority"
        ]
        != "NONE"
    ):
        errors.append(
            "package may not carry publication authority"
        )

    unsigned = dict(
        package
    )

    supplied_digest = unsigned.pop(
        "package_digest"
    )

    if (
        supplied_digest
        != transport_digest(
            unsigned
        )
    ):
        errors.append(
            "editorial visual package digest mismatch"
        )

    return tuple(
        errors
    )
