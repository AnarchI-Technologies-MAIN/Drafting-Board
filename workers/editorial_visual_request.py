"""Foundry-owned editorial visual request contract.

A reviewed article may authorize a bounded image handoff.

It does not grant:
- factual authority to an image,
- human approval,
- publication authority,
- execution authority.

The reviewed article supplies bounded truth.
The visual request supplies representation intent.

Illustration may transform representation.
It may not increase epistemic strength.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Iterable

from editorial_review_artifact import (
    REVIEW_ARTIFACT_VERSION,
    ReviewedArticleArtifact,
    validate_artifact,
)


EDITORIAL_VISUAL_REQUEST_VERSION = (
    "anarchi.editorial-visual-request.v1"
)

_HEX64 = re.compile(
    r"^[0-9a-f]{64}$"
)


class VisualPurpose(str, Enum):
    DECORATIVE = "DECORATIVE"
    CONCEPTUAL = "CONCEPTUAL"
    EXPLANATORY = "EXPLANATORY"
    FACTUAL = "FACTUAL"


@dataclass(frozen=True)
class ReviewedArticleBinding:
    schema_version: str
    artifact_digest: str
    article_digest: str


@dataclass(frozen=True)
class RepresentationConstraints:
    may_introduce_new_claims: bool = False
    may_strengthen_claims: bool = False
    may_change_claims: bool = False
    factual_content_requires_bound_claims: bool = True


@dataclass(frozen=True)
class EditorialVisualRequest:
    schema_version: str
    request_id: str

    reviewed_article_binding: ReviewedArticleBinding

    visual_purpose: VisualPurpose
    bound_claim_ids: tuple[str, ...]
    visual_instruction: str

    representation_constraints: RepresentationConstraints

    authority_state: str
    evidentiary_authority: str
    human_approval: str
    publication_authority: str

    @property
    def request_digest(self) -> str:
        return digest_payload(
            request_payload(self)
        )

    @property
    def requires_semantic_visual_validation(self) -> bool:
        return self.visual_purpose in {
            VisualPurpose.EXPLANATORY,
            VisualPurpose.FACTUAL,
        }

    @property
    def grants_execution(self) -> bool:
        return False

    @property
    def grants_human_approval(self) -> bool:
        return False

    @property
    def grants_publication(self) -> bool:
        return False

    @property
    def grants_evidentiary_authority(self) -> bool:
        return False


def canonical_json(
    payload: dict,
) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def digest_payload(
    payload: dict,
) -> str:
    return hashlib.sha256(
        canonical_json(
            payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def request_payload(
    request: EditorialVisualRequest,
) -> dict:
    return {
        "schema_version": (
            request.schema_version
        ),
        "request_id": (
            request.request_id
        ),
        "reviewed_article_binding": {
            "schema_version": (
                request.reviewed_article_binding.schema_version
            ),
            "artifact_digest": (
                request.reviewed_article_binding.artifact_digest
            ),
            "article_digest": (
                request.reviewed_article_binding.article_digest
            ),
        },
        "visual_purpose": (
            request.visual_purpose.value
        ),
        "bound_claim_ids": list(
            request.bound_claim_ids
        ),
        "visual_instruction": (
            request.visual_instruction
        ),
        "representation_constraints": {
            "may_introduce_new_claims": (
                request.representation_constraints
                .may_introduce_new_claims
            ),
            "may_strengthen_claims": (
                request.representation_constraints
                .may_strengthen_claims
            ),
            "may_change_claims": (
                request.representation_constraints
                .may_change_claims
            ),
            "factual_content_requires_bound_claims": (
                request.representation_constraints
                .factual_content_requires_bound_claims
            ),
        },
        "authority_state": (
            request.authority_state
        ),
        "evidentiary_authority": (
            request.evidentiary_authority
        ),
        "human_approval": (
            request.human_approval
        ),
        "publication_authority": (
            request.publication_authority
        ),
    }


def _normalize_claim_ids(
    claim_ids: Iterable[str],
) -> tuple[str, ...]:
    values = tuple(
        sorted(
            set(
                claim_ids
            )
        )
    )

    for claim_id in values:
        if (
            not isinstance(
                claim_id,
                str,
            )
            or not claim_id.strip()
        ):
            raise ValueError(
                "claim IDs must be non-empty strings"
            )

    return values


def validate_request(
    request: EditorialVisualRequest,
    artifact: ReviewedArticleArtifact,
) -> tuple[str, ...]:
    errors: list[str] = []

    artifact_errors = validate_artifact(
        artifact
    )

    if artifact_errors:
        errors.append(
            "reviewed article artifact is invalid"
        )

    if not artifact.image_handoff_permitted:
        errors.append(
            "reviewed article does not permit image handoff"
        )

    if (
        request.schema_version
        != EDITORIAL_VISUAL_REQUEST_VERSION
    ):
        errors.append(
            "visual request schema version mismatch"
        )

    binding = request.reviewed_article_binding

    if (
        binding.schema_version
        != REVIEW_ARTIFACT_VERSION
    ):
        errors.append(
            "reviewed article schema binding mismatch"
        )

    if (
        binding.artifact_digest
        != artifact.artifact_digest
    ):
        errors.append(
            "reviewed artifact digest binding mismatch"
        )

    if (
        binding.article_digest
        != artifact.article_digest
    ):
        errors.append(
            "reviewed article digest binding mismatch"
        )

    if (
        _HEX64.fullmatch(
            binding.artifact_digest
        )
        is None
    ):
        errors.append(
            "artifact digest representation invalid"
        )

    if (
        not isinstance(
            request.visual_instruction,
            str,
        )
        or not request.visual_instruction.strip()
    ):
        errors.append(
            "visual instruction must be non-empty"
        )

    if (
        len(
            request.visual_instruction
        )
        > 4096
    ):
        errors.append(
            "visual instruction exceeds 4096 characters"
        )

    if (
        request.authority_state
        != "REQUEST_ONLY"
    ):
        errors.append(
            "visual request authority must remain REQUEST_ONLY"
        )

    if (
        request.evidentiary_authority
        != "NONE"
    ):
        errors.append(
            "visual request may not carry evidentiary authority"
        )

    if (
        request.human_approval
        != "NONE"
    ):
        errors.append(
            "visual request may not carry human approval"
        )

    if (
        request.publication_authority
        != "NONE"
    ):
        errors.append(
            "visual request may not carry publication authority"
        )

    constraints = (
        request.representation_constraints
    )

    if constraints.may_introduce_new_claims:
        errors.append(
            "visual request may not introduce new claims"
        )

    if constraints.may_strengthen_claims:
        errors.append(
            "visual request may not strengthen reviewed claims"
        )

    if constraints.may_change_claims:
        errors.append(
            "visual request may not change reviewed claims"
        )

    if (
        not constraints
        .factual_content_requires_bound_claims
    ):
        errors.append(
            "factual visual content must require claim bindings"
        )

    material_ids = set(
        artifact.material_claim_ids
    )

    bound_ids = set(
        request.bound_claim_ids
    )

    unknown_ids = sorted(
        bound_ids.difference(
            material_ids
        )
    )

    if unknown_ids:
        errors.append(
            "visual request references unknown or "
            "non-material claim IDs: "
            + ",".join(
                unknown_ids
            )
        )

    if (
        request.visual_purpose
        in {
            VisualPurpose.EXPLANATORY,
            VisualPurpose.FACTUAL,
        }
        and not bound_ids
    ):
        errors.append(
            request.visual_purpose.value
            + " visual requires at least one "
            "material reviewed claim binding"
        )

    return tuple(
        errors
    )


def build_editorial_visual_request(
    *,
    artifact: ReviewedArticleArtifact,
    visual_purpose: VisualPurpose,
    visual_instruction: str,
    bound_claim_ids: Iterable[str] = (),
) -> EditorialVisualRequest:
    artifact_errors = validate_artifact(
        artifact
    )

    if artifact_errors:
        raise ValueError(
            "invalid reviewed article artifact: "
            + "; ".join(
                artifact_errors
            )
        )

    if not artifact.image_handoff_permitted:
        raise ValueError(
            "reviewed article does not permit image handoff"
        )

    normalized_claim_ids = (
        _normalize_claim_ids(
            bound_claim_ids
        )
    )

    identity_seed = {
        "artifact_digest": (
            artifact.artifact_digest
        ),
        "article_digest": (
            artifact.article_digest
        ),
        "visual_purpose": (
            visual_purpose.value
        ),
        "bound_claim_ids": list(
            normalized_claim_ids
        ),
        "visual_instruction": (
            visual_instruction
        ),
    }

    request_id = (
        "editorial_visual_"
        + digest_payload(
            identity_seed
        )[:24]
    )

    request = EditorialVisualRequest(
        schema_version=(
            EDITORIAL_VISUAL_REQUEST_VERSION
        ),
        request_id=request_id,
        reviewed_article_binding=(
            ReviewedArticleBinding(
                schema_version=(
                    artifact.schema_version
                ),
                artifact_digest=(
                    artifact.artifact_digest
                ),
                article_digest=(
                    artifact.article_digest
                ),
            )
        ),
        visual_purpose=visual_purpose,
        bound_claim_ids=(
            normalized_claim_ids
        ),
        visual_instruction=(
            visual_instruction
        ),
        representation_constraints=(
            RepresentationConstraints()
        ),
        authority_state="REQUEST_ONLY",
        evidentiary_authority="NONE",
        human_approval="NONE",
        publication_authority="NONE",
    )

    errors = validate_request(
        request,
        artifact,
    )

    if errors:
        raise ValueError(
            "; ".join(
                errors
            )
        )

    return request
