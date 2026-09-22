"""Authenticated-boundary transport wrapper for SocialVisualEnvelope.

The wrapper preserves campaign/social ancestry around the already-proven
EditorialVisualPackage.

Authentication is not granted here. It belongs to data-intake.v2 and the
source/indexing trust boundary.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Iterable

from editorial_review_artifact import (
    ReviewedArticleArtifact,
)

from editorial_visual_package import (
    build_package,
    validate_package as validate_editorial_package,
)

from social_atomic_review import (
    ReviewedSocialArtifact,
)

from social_visual_envelope import (
    SocialVisualEnvelope,
    envelope_payload,
    validate_social_visual_envelope,
)


SOCIAL_VISUAL_TRANSPORT_VERSION = (
    "anarchi.social-visual-transport-package.v1"
)


class SocialVisualTransportFailure(
    Exception
):
    pass


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise SocialVisualTransportFailure(
            message
        )


def canonical(
    value: Any,
) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode(
        "utf-8"
    )


def transport_digest(
    value: Any,
) -> str:
    return (
        "sha256:"
        + sha256(
            canonical(
                value
            )
        ).hexdigest()
    )


def serializable_envelope(
    envelope: SocialVisualEnvelope,
) -> dict[str, Any]:
    payload = envelope_payload(
        envelope
    )

    return {
        **payload,
        "envelope_digest": (
            envelope.envelope_digest
        ),
    }


def build_social_visual_transport(
    *,
    envelope: SocialVisualEnvelope,
    reviewed: ReviewedSocialArtifact,
    draft: dict[str, Any],
    request: dict[str, Any],
    package: dict[str, Any],
    source_artifacts: Iterable[
        ReviewedArticleArtifact
    ],
) -> dict[str, Any]:
    source_artifacts = tuple(
        source_artifacts
    )

    try:
        validate_social_visual_envelope(
            envelope,
            reviewed=reviewed,
            draft=draft,
            request=request,
            package=package,
            source_artifacts=source_artifacts,
        )
    except Exception as exc:
        raise SocialVisualTransportFailure(
            "social visual envelope invalid"
        ) from exc

    inner = build_package(
        artifact=reviewed.review_core,
        request=envelope.visual_request,
    )

    errors = validate_editorial_package(
        inner,
        artifact=reviewed.review_core,
        request=envelope.visual_request,
    )

    require(
        not errors,
        (
            "inner editorial package invalid: "
            + "; ".join(
                errors
            )
        ),
    )

    unsigned = {
        "schema": (
            SOCIAL_VISUAL_TRANSPORT_VERSION
        ),
        "social_visual_envelope": (
            serializable_envelope(
                envelope
            )
        ),
        "inner_editorial_package": (
            inner
        ),
        "inner_editorial_package_digest": (
            inner[
                "package_digest"
            ]
        ),
        "authority_state": (
            "TRANSPORT_ONLY"
        ),
        "evidentiary_authority": (
            "NONE"
        ),
        "factual_authority": (
            "NONE"
        ),
        "human_approval": (
            "NONE"
        ),
        "publication_authority": (
            "NONE"
        ),
    }

    return {
        **unsigned,
        "transport_digest": (
            transport_digest(
                unsigned
            )
        ),
    }


def validate_social_visual_transport(
    value: Any,
    *,
    envelope: SocialVisualEnvelope,
    reviewed: ReviewedSocialArtifact,
    draft: dict[str, Any],
    request: dict[str, Any],
    package: dict[str, Any],
    source_artifacts: Iterable[
        ReviewedArticleArtifact
    ],
) -> dict[str, Any]:
    require(
        isinstance(
            value,
            dict,
        ),
        "social visual transport invalid",
    )

    required = {
        "schema",
        "social_visual_envelope",
        "inner_editorial_package",
        "inner_editorial_package_digest",
        "authority_state",
        "evidentiary_authority",
        "factual_authority",
        "human_approval",
        "publication_authority",
        "transport_digest",
    }

    require(
        set(
            value
        )
        == required,
        "social visual transport fields invalid",
    )

    require(
        value[
            "schema"
        ]
        == SOCIAL_VISUAL_TRANSPORT_VERSION,
        "social visual transport schema invalid",
    )

    source_artifacts = tuple(
        source_artifacts
    )

    try:
        validate_social_visual_envelope(
            envelope,
            reviewed=reviewed,
            draft=draft,
            request=request,
            package=package,
            source_artifacts=source_artifacts,
        )
    except Exception as exc:
        raise SocialVisualTransportFailure(
            "social visual envelope ancestry invalid"
        ) from exc

    require(
        value[
            "social_visual_envelope"
        ]
        == serializable_envelope(
            envelope
        ),
        "social visual envelope transport binding mismatch",
    )

    expected_inner = build_package(
        artifact=reviewed.review_core,
        request=envelope.visual_request,
    )

    require(
        value[
            "inner_editorial_package"
        ]
        == expected_inner,
        "inner editorial package substitution detected",
    )

    require(
        value[
            "inner_editorial_package_digest"
        ]
        == expected_inner[
            "package_digest"
        ],
        "inner editorial package digest binding mismatch",
    )

    unsigned = dict(
        value
    )

    supplied = unsigned.pop(
        "transport_digest"
    )

    require(
        supplied
        == transport_digest(
            unsigned
        ),
        "social visual transport digest invalid",
    )

    require(
        value[
            "authority_state"
        ]
        == "TRANSPORT_ONLY",
        "transport authority invalid",
    )

    for field in (
        "evidentiary_authority",
        "factual_authority",
        "human_approval",
        "publication_authority",
    ):
        require(
            value[
                field
            ]
            == "NONE",
            field
            + " forbidden",
        )

    return dict(
        value
    )
