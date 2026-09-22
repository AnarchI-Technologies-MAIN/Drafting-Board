"""Editorial visual handoff transport membrane.

Foundry-native SHA-256 identities use:

    <64 lowercase hex>

Illustration transport identities use:

    sha256:<64 lowercase hex>

This module may normalize representation.

It may not:
- reinterpret malformed identity,
- change underlying identity,
- change claims,
- strengthen claims,
- grant evidentiary authority,
- grant approval,
- grant publication authority.
"""

from __future__ import annotations

import hashlib
import json
import re

from editorial_review_artifact import (
    ReviewedArticleArtifact,
)
from editorial_visual_request import (
    EDITORIAL_VISUAL_REQUEST_VERSION,
    EditorialVisualRequest,
    request_payload,
    validate_request,
)


EDITORIAL_VISUAL_HANDOFF_VERSION = (
    "anarchi.editorial-visual-handoff.v1"
)

_NATIVE_SHA256 = re.compile(
    r"^[0-9a-f]{64}$"
)

_TRANSPORT_SHA256 = re.compile(
    r"^sha256:[0-9a-f]{64}$"
)


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


def transport_digest(
    payload: dict,
) -> str:
    return (
        "sha256:"
        + digest_payload(
            payload
        )
    )


def to_transport_digest(
    native_digest: str,
) -> str:
    if (
        not isinstance(
            native_digest,
            str,
        )
        or _NATIVE_SHA256.fullmatch(
            native_digest
        )
        is None
    ):
        raise ValueError(
            "native digest must be exactly "
            "64 lowercase hexadecimal characters"
        )

    return (
        "sha256:"
        + native_digest
    )


def from_transport_digest(
    transport_value: str,
) -> str:
    if (
        not isinstance(
            transport_value,
            str,
        )
        or _TRANSPORT_SHA256.fullmatch(
            transport_value
        )
        is None
    ):
        raise ValueError(
            "transport digest must be exactly "
            "sha256:<64 lowercase hexadecimal characters>"
        )

    return transport_value[
        len("sha256:"):
    ]


def handoff_payload(
    request: EditorialVisualRequest,
) -> dict:
    source = request_payload(
        request
    )

    reviewed = source[
        "reviewed_article_binding"
    ]

    return {
        "schema": (
            EDITORIAL_VISUAL_HANDOFF_VERSION
        ),
        "source_request_binding": {
            "schema_version": (
                EDITORIAL_VISUAL_REQUEST_VERSION
            ),
            "request_id": (
                request.request_id
            ),
            "request_digest": (
                to_transport_digest(
                    request.request_digest
                )
            ),
        },
        "reviewed_article_binding": {
            "schema_version": (
                reviewed[
                    "schema_version"
                ]
            ),
            "artifact_digest": (
                to_transport_digest(
                    reviewed[
                        "artifact_digest"
                    ]
                )
            ),
            "article_digest": (
                to_transport_digest(
                    reviewed[
                        "article_digest"
                    ]
                )
            ),
        },
        "visual_purpose": (
            source[
                "visual_purpose"
            ]
        ),
        "bound_claim_ids": list(
            source[
                "bound_claim_ids"
            ]
        ),
        "visual_instruction": (
            source[
                "visual_instruction"
            ]
        ),
        "representation_constraints": dict(
            source[
                "representation_constraints"
            ]
        ),
        "authority_state": (
            source[
                "authority_state"
            ]
        ),
        "evidentiary_authority": (
            source[
                "evidentiary_authority"
            ]
        ),
        "human_approval": (
            source[
                "human_approval"
            ]
        ),
        "publication_authority": (
            source[
                "publication_authority"
            ]
        ),
    }


def build_handoff(
    request: EditorialVisualRequest,
    artifact: ReviewedArticleArtifact,
) -> dict:
    errors = validate_request(
        request,
        artifact,
    )

    if errors:
        raise ValueError(
            "invalid editorial visual request: "
            + "; ".join(
                errors
            )
        )

    payload = handoff_payload(
        request
    )

    envelope = dict(
        payload
    )

    envelope[
        "handoff_digest"
    ] = transport_digest(
        payload
    )

    return envelope


def validate_handoff(
    envelope: dict,
    request: EditorialVisualRequest,
    artifact: ReviewedArticleArtifact,
) -> tuple[str, ...]:
    errors: list[str] = []

    source_errors = validate_request(
        request,
        artifact,
    )

    if source_errors:
        errors.append(
            "source editorial visual request invalid"
        )

    if not isinstance(
        envelope,
        dict,
    ):
        return (
            "handoff envelope must be an object",
        )

    expected_fields = {
        "schema",
        "source_request_binding",
        "reviewed_article_binding",
        "visual_purpose",
        "bound_claim_ids",
        "visual_instruction",
        "representation_constraints",
        "authority_state",
        "evidentiary_authority",
        "human_approval",
        "publication_authority",
        "handoff_digest",
    }

    if set(
        envelope
    ) != expected_fields:
        errors.append(
            "handoff fields invalid"
        )

        return tuple(
            errors
        )

    if (
        envelope[
            "schema"
        ]
        != EDITORIAL_VISUAL_HANDOFF_VERSION
    ):
        errors.append(
            "handoff schema mismatch"
        )

    source_binding = envelope[
        "source_request_binding"
    ]

    reviewed_binding = envelope[
        "reviewed_article_binding"
    ]

    if (
        not isinstance(
            source_binding,
            dict,
        )
        or set(
            source_binding
        )
        != {
            "schema_version",
            "request_id",
            "request_digest",
        }
    ):
        errors.append(
            "source request binding invalid"
        )

        return tuple(
            errors
        )

    if (
        not isinstance(
            reviewed_binding,
            dict,
        )
        or set(
            reviewed_binding
        )
        != {
            "schema_version",
            "artifact_digest",
            "article_digest",
        }
    ):
        errors.append(
            "reviewed article binding invalid"
        )

        return tuple(
            errors
        )

    try:
        request_native = (
            from_transport_digest(
                source_binding[
                    "request_digest"
                ]
            )
        )

        artifact_native = (
            from_transport_digest(
                reviewed_binding[
                    "artifact_digest"
                ]
            )
        )

        article_native = (
            from_transport_digest(
                reviewed_binding[
                    "article_digest"
                ]
            )
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        errors.append(
            "transport digest representation invalid"
        )

        return tuple(
            errors
        )

    if (
        request_native
        != request.request_digest
    ):
        errors.append(
            "source request identity changed in transport"
        )

    if (
        artifact_native
        != artifact.artifact_digest
    ):
        errors.append(
            "reviewed artifact identity changed in transport"
        )

    if (
        article_native
        != artifact.article_digest
    ):
        errors.append(
            "article identity changed in transport"
        )

    if (
        source_binding[
            "request_id"
        ]
        != request.request_id
    ):
        errors.append(
            "source request ID mismatch"
        )

    if (
        source_binding[
            "schema_version"
        ]
        != EDITORIAL_VISUAL_REQUEST_VERSION
    ):
        errors.append(
            "source request schema binding mismatch"
        )

    source = request_payload(
        request
    )

    fields_to_preserve = (
        "visual_purpose",
        "bound_claim_ids",
        "visual_instruction",
        "representation_constraints",
        "authority_state",
        "evidentiary_authority",
        "human_approval",
        "publication_authority",
    )

    for field in fields_to_preserve:
        expected = source[
            field
        ]

        if field == "bound_claim_ids":
            expected = list(
                expected
            )

        if (
            envelope[
                field
            ]
            != expected
        ):
            errors.append(
                "transport changed field: "
                + field
            )

    unsigned = dict(
        envelope
    )

    supplied_digest = unsigned.pop(
        "handoff_digest"
    )

    if (
        supplied_digest
        != transport_digest(
            unsigned
        )
    ):
        errors.append(
            "handoff digest mismatch"
        )

    return tuple(
        errors
    )
