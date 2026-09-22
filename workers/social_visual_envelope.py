"""Reviewed Social Artifact -> Editorial Visual Request envelope.

The envelope preserves campaign/social ancestry around the already-proven
editorial visual request contract.

Laws:

- Reviewed social copy must validate against its original ancestry.
- Existing EditorialVisualRequest remains the visual semantics core.
- Campaign ancestry is preserved outside that reusable core.
- The envelope grants no evidentiary, factual, human, execution, or
  publication authority.
- Rebinding campaign ancestry changes envelope identity.
- Rebinding the visual request changes envelope identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable

from editorial_review_artifact import (
    ReviewedArticleArtifact,
)

from editorial_visual_request import (
    EditorialVisualRequest,
    VisualPurpose,
    build_editorial_visual_request,
    request_payload,
    validate_request,
)

from social_atomic_review import (
    ReviewedSocialArtifact,
    validate_reviewed_social_artifact,
)


SOCIAL_VISUAL_ENVELOPE_VERSION = (
    "anarchi.social-visual-envelope.v1"
)


class SocialVisualEnvelopeFailure(
    Exception
):
    pass


@dataclass(
    frozen=True
)
class SocialVisualAncestry:
    reviewed_social_digest: str
    draft_id: str
    draft_digest: str
    materialization_request_digest: str
    campaign_package_digest: str
    slot_id: str
    reviewed_core_artifact_digest: str


@dataclass(
    frozen=True
)
class SocialVisualEnvelope:
    schema_version: str
    ancestry: SocialVisualAncestry
    visual_request: EditorialVisualRequest
    visual_request_id: str
    visual_request_digest: str
    authority_state: str
    evidentiary_authority: str
    factual_authority: str
    human_approval: str
    publication_authority: str
    envelope_digest: str


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise SocialVisualEnvelopeFailure(
            message
        )


def canonical(
    value: Any,
) -> bytes:
    def default(
        item: Any,
    ) -> Any:
        if hasattr(
            item,
            "value",
        ):
            return item.value

        if hasattr(
            item,
            "__dataclass_fields__",
        ):
            return {
                name: getattr(
                    item,
                    name,
                )
                for name
                in item.__dataclass_fields__
            }

        raise TypeError(
            type(
                item
            ).__name__
        )

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=default,
    ).encode(
        "utf-8"
    )


def digest(
    value: Any,
) -> str:
    return sha256(
        canonical(
            value
        )
    ).hexdigest()


def ancestry_from_reviewed(
    reviewed: ReviewedSocialArtifact,
) -> SocialVisualAncestry:
    return SocialVisualAncestry(
        reviewed_social_digest=(
            reviewed.reviewed_social_digest
        ),
        draft_id=(
            reviewed.draft_id
        ),
        draft_digest=(
            reviewed.draft_digest
        ),
        materialization_request_digest=(
            reviewed.materialization_request_digest
        ),
        campaign_package_digest=(
            reviewed.package_digest
        ),
        slot_id=(
            reviewed.slot_id
        ),
        reviewed_core_artifact_digest=(
            reviewed.review_core.artifact_digest
        ),
    )


def envelope_payload(
    envelope: SocialVisualEnvelope,
) -> dict[str, Any]:
    return {
        "schema_version": (
            envelope.schema_version
        ),
        "ancestry": {
            "reviewed_social_digest": (
                envelope.ancestry.reviewed_social_digest
            ),
            "draft_id": (
                envelope.ancestry.draft_id
            ),
            "draft_digest": (
                envelope.ancestry.draft_digest
            ),
            "materialization_request_digest": (
                envelope.ancestry.materialization_request_digest
            ),
            "campaign_package_digest": (
                envelope.ancestry.campaign_package_digest
            ),
            "slot_id": (
                envelope.ancestry.slot_id
            ),
            "reviewed_core_artifact_digest": (
                envelope.ancestry.reviewed_core_artifact_digest
            ),
        },
        "visual_request": (
            request_payload(
                envelope.visual_request
            )
        ),
        "visual_request_id": (
            envelope.visual_request_id
        ),
        "visual_request_digest": (
            envelope.visual_request_digest
        ),
        "authority_state": (
            envelope.authority_state
        ),
        "evidentiary_authority": (
            envelope.evidentiary_authority
        ),
        "factual_authority": (
            envelope.factual_authority
        ),
        "human_approval": (
            envelope.human_approval
        ),
        "publication_authority": (
            envelope.publication_authority
        ),
    }


def build_social_visual_envelope(
    *,
    reviewed: ReviewedSocialArtifact,
    draft: dict[str, Any],
    request: dict[str, Any],
    package: dict[str, Any],
    source_artifacts: Iterable[
        ReviewedArticleArtifact
    ],
    visual_purpose: VisualPurpose,
    visual_instruction: str,
    bound_claim_ids: Iterable[str] = (),
) -> SocialVisualEnvelope:
    source_artifacts = tuple(
        source_artifacts
    )

    try:
        validate_reviewed_social_artifact(
            reviewed,
            draft=draft,
            request=request,
            package=package,
            source_artifacts=source_artifacts,
        )
    except Exception as exc:
        raise SocialVisualEnvelopeFailure(
            "reviewed social ancestry validation failed"
        ) from exc

    require(
        reviewed.authority_state
        == "TEXT_REVIEWED_ONLY",
        "reviewed social authority state invalid",
    )

    require(
        reviewed.factual_authority
        == "NONE",
        "reviewed social factual authority forbidden",
    )

    require(
        reviewed.human_approval
        == "NONE",
        "reviewed social human approval forbidden",
    )

    require(
        reviewed.publication_authority
        == "NONE",
        "reviewed social publication authority forbidden",
    )

    visual_request = (
        build_editorial_visual_request(
            artifact=(
                reviewed.review_core
            ),
            visual_purpose=(
                visual_purpose
            ),
            visual_instruction=(
                visual_instruction
            ),
            bound_claim_ids=(
                bound_claim_ids
            ),
        )
    )

    errors = validate_request(
        visual_request,
        reviewed.review_core,
    )

    require(
        not errors,
        (
            "editorial visual request invalid: "
            + "; ".join(
                errors
            )
        ),
    )

    ancestry = ancestry_from_reviewed(
        reviewed
    )

    envelope = SocialVisualEnvelope(
        schema_version=(
            SOCIAL_VISUAL_ENVELOPE_VERSION
        ),
        ancestry=(
            ancestry
        ),
        visual_request=(
            visual_request
        ),
        visual_request_id=(
            visual_request.request_id
        ),
        visual_request_digest=(
            visual_request.request_digest
        ),
        authority_state=(
            "REQUEST_ENVELOPE_ONLY"
        ),
        evidentiary_authority=(
            "NONE"
        ),
        factual_authority=(
            "NONE"
        ),
        human_approval=(
            "NONE"
        ),
        publication_authority=(
            "NONE"
        ),
        envelope_digest="",
    )

    sealed = SocialVisualEnvelope(
        schema_version=(
            envelope.schema_version
        ),
        ancestry=(
            envelope.ancestry
        ),
        visual_request=(
            envelope.visual_request
        ),
        visual_request_id=(
            envelope.visual_request_id
        ),
        visual_request_digest=(
            envelope.visual_request_digest
        ),
        authority_state=(
            envelope.authority_state
        ),
        evidentiary_authority=(
            envelope.evidentiary_authority
        ),
        factual_authority=(
            envelope.factual_authority
        ),
        human_approval=(
            envelope.human_approval
        ),
        publication_authority=(
            envelope.publication_authority
        ),
        envelope_digest=(
            digest(
                envelope_payload(
                    envelope
                )
            )
        ),
    )

    return sealed


def validate_social_visual_envelope(
    envelope: SocialVisualEnvelope,
    *,
    reviewed: ReviewedSocialArtifact,
    draft: dict[str, Any],
    request: dict[str, Any],
    package: dict[str, Any],
    source_artifacts: Iterable[
        ReviewedArticleArtifact
    ],
) -> SocialVisualEnvelope:
    require(
        isinstance(
            envelope,
            SocialVisualEnvelope,
        ),
        "social visual envelope invalid",
    )

    require(
        envelope.schema_version
        == SOCIAL_VISUAL_ENVELOPE_VERSION,
        "social visual envelope schema invalid",
    )

    source_artifacts = tuple(
        source_artifacts
    )

    try:
        validate_reviewed_social_artifact(
            reviewed,
            draft=draft,
            request=request,
            package=package,
            source_artifacts=source_artifacts,
        )
    except Exception as exc:
        raise SocialVisualEnvelopeFailure(
            "reviewed social ancestry validation failed"
        ) from exc

    expected_ancestry = (
        ancestry_from_reviewed(
            reviewed
        )
    )

    require(
        envelope.ancestry
        == expected_ancestry,
        "social visual ancestry mismatch",
    )

    require(
        envelope.visual_request_id
        == envelope.visual_request.request_id,
        "visual request ID binding mismatch",
    )

    require(
        envelope.visual_request_digest
        == envelope.visual_request.request_digest,
        "visual request digest binding mismatch",
    )

    errors = validate_request(
        envelope.visual_request,
        reviewed.review_core,
    )

    require(
        not errors,
        (
            "embedded editorial visual request invalid: "
            + "; ".join(
                errors
            )
        ),
    )

    require(
        envelope.visual_request.reviewed_article_binding.artifact_digest
        == reviewed.review_core.artifact_digest,
        "visual request reviewed-core artifact binding mismatch",
    )

    require(
        envelope.visual_request.reviewed_article_binding.article_digest
        == reviewed.review_core.article_digest,
        "visual request reviewed-core text identity mismatch",
    )

    require(
        envelope.ancestry.reviewed_core_artifact_digest
        == reviewed.review_core.artifact_digest,
        "social ancestry reviewed-core identity mismatch",
    )

    require(
        envelope.authority_state
        == "REQUEST_ENVELOPE_ONLY",
        "social visual envelope authority invalid",
    )

    require(
        envelope.evidentiary_authority
        == "NONE",
        "social visual evidentiary authority forbidden",
    )

    require(
        envelope.factual_authority
        == "NONE",
        "social visual factual authority forbidden",
    )

    require(
        envelope.human_approval
        == "NONE",
        "social visual human approval forbidden",
    )

    require(
        envelope.publication_authority
        == "NONE",
        "social visual publication authority forbidden",
    )

    require(
        envelope.envelope_digest
        == digest(
            envelope_payload(
                envelope
            )
        ),
        "social visual envelope digest invalid",
    )

    return envelope
