"""Social artifact materialization boundary.

A social distribution slot is planning.

A social artifact draft is materialized language.

Materialized language possesses zero factual authority until it has
passed Atomic Review.

This module does not generate language. It defines the contract a
future Social Distribution cognition substrate must obey.
"""

from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Iterable

from social_distribution import (
    validate_weekly_package,
)


MATERIALIZATION_REQUEST_VERSION = (
    "anarchi.social-artifact-materialization-request.v1"
)

SOCIAL_ARTIFACT_DRAFT_VERSION = (
    "anarchi.social-artifact-draft.v1"
)

_HEX64 = re.compile(
    r"^[0-9a-f]{64}$"
)


class SocialArtifactFailure(
    Exception
):
    pass


def canonical(
    value: Any,
) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(
    value: Any,
) -> str:
    return sha256(
        canonical(
            value
        )
    ).hexdigest()


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise SocialArtifactFailure(
            message
        )


def verify_bound_digest(
    value: dict[str, Any],
    field: str,
    message: str,
) -> None:
    supplied = value.get(
        field
    )

    unsigned = dict(
        value
    )

    unsigned.pop(
        field,
        None,
    )

    require(
        supplied
        == digest(
            unsigned
        ),
        message,
    )


def find_slot(
    package: dict[str, Any],
    slot_id: str,
) -> dict[str, Any]:
    matches = [
        slot
        for slot in package[
            "distribution_slots"
        ]
        if slot[
            "slot_id"
        ]
        == slot_id
    ]

    require(
        len(
            matches
        )
        == 1,
        "social slot identity must resolve exactly once",
    )

    return dict(
        matches[0]
    )


def build_materialization_request(
    *,
    package: dict[str, Any],
    artifacts: Iterable[Any],
    slot_id: str,
) -> dict[str, Any]:
    try:
        package = validate_weekly_package(
            package,
            artifacts=artifacts,
        )
    except Exception as exc:
        raise SocialArtifactFailure(
            "weekly package validation failed"
        ) from exc

    require(
        package[
            "planning_resolution"
        ]
        in {
            "READY_FOR_ADJUDICATION",
            "MATERIALIZATION_READY",
        },
        "structured-intent package is not materialization eligible",
    )

    require(
        isinstance(
            slot_id,
            str,
        )
        and bool(
            slot_id
        ),
        "social slot ID invalid",
    )

    slot = find_slot(
        package,
        slot_id,
    )

    request_identity = {
        "package_digest": (
            package[
                "package_digest"
            ]
        ),
        "slot_id": (
            slot[
                "slot_id"
            ]
        ),
    }

    request = {
        "schema": (
            MATERIALIZATION_REQUEST_VERSION
        ),
        "request_id": (
            "social_materialization_"
            + digest(
                request_identity
            )[:24]
        ),
        "campaign_binding": {
            "campaign_id": (
                package[
                    "campaign_id"
                ]
            ),
            "package_id": (
                package[
                    "package_id"
                ]
            ),
            "package_digest": (
                package[
                    "package_digest"
                ]
            ),
            "package_revision": (
                package[
                    "revision"
                ]
            ),
            "week_index": (
                package[
                    "week_index"
                ]
            ),
        },
        "slot_binding": {
            "slot_id": (
                slot[
                    "slot_id"
                ]
            ),
            "scheduled_at": (
                slot[
                    "scheduled_at"
                ]
            ),
            "platform": (
                slot[
                    "platform"
                ]
            ),
            "format": (
                slot[
                    "format"
                ]
            ),
            "platform_profile": (
                slot[
                    "platform_profile"
                ]
            ),
            "content_role": (
                slot[
                    "content_role"
                ]
            ),
            "hook_posture": (
                slot[
                    "hook_posture"
                ]
            ),
            "caption_posture": (
                slot[
                    "caption_posture"
                ]
            ),
            "cta_posture": (
                slot[
                    "cta_posture"
                ]
            ),
            "visual_purpose": (
                slot[
                    "visual_purpose"
                ]
            ),
        },
        "allowed_truth_bindings": (
            slot[
                "claim_bindings"
            ]
        ),
        "generation_constraints": {
            "may_introduce_unbound_factual_claims": False,
            "may_strengthen_reviewed_claims": False,
            "may_create_evidentiary_authority": False,
            "may_create_human_approval": False,
            "may_create_publication_authority": False,
            "atomic_review_required": True,
            "visual_semantic_review_required": True,
        },
        "authority_state": (
            "MATERIALIZATION_REQUEST_ONLY"
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

    request[
        "request_digest"
    ] = digest(
        request
    )

    return request


def validate_materialization_request(
    request: Any,
    *,
    package: dict[str, Any],
    artifacts: Iterable[Any],
) -> dict[str, Any]:
    require(
        isinstance(
            request,
            dict,
        ),
        "social materialization request invalid",
    )

    expected_fields = {
        "schema",
        "request_id",
        "campaign_binding",
        "slot_binding",
        "allowed_truth_bindings",
        "generation_constraints",
        "authority_state",
        "factual_authority",
        "human_approval",
        "publication_authority",
        "request_digest",
    }

    require(
        set(
            request
        )
        == expected_fields,
        "social materialization request fields invalid",
    )

    require(
        request[
            "schema"
        ]
        == MATERIALIZATION_REQUEST_VERSION,
        "social materialization request schema invalid",
    )

    verify_bound_digest(
        request,
        "request_digest",
        "social materialization request digest invalid",
    )

    slot_id = request[
        "slot_binding"
    ][
        "slot_id"
    ]

    expected = build_materialization_request(
        package=package,
        artifacts=artifacts,
        slot_id=slot_id,
    )

    require(
        request
        == expected,
        "social materialization request does not match canonical package slot",
    )

    return dict(
        request
    )


def normalize_copy(
    copy: Any,
) -> dict[str, Any]:
    require(
        isinstance(
            copy,
            dict,
        ),
        "social copy payload invalid",
    )

    expected = {
        "headline",
        "body",
        "cta",
        "alt_text",
        "destination",
    }

    require(
        set(
            copy
        )
        == expected,
        "social copy fields invalid",
    )

    normalized: dict[
        str,
        str | None
    ] = {}

    for field in (
        "headline",
        "body",
        "cta",
        "alt_text",
        "destination",
    ):
        value = copy[
            field
        ]

        require(
            value is None
            or (
                isinstance(
                    value,
                    str,
                )
                and bool(
                    value.strip()
                )
            ),
            "social copy field must be null or non-empty text",
        )

        normalized[
            field
        ] = value

    require(
        any(
            normalized[
                field
            ]
            is not None
            for field in (
                "headline",
                "body",
                "cta",
                "alt_text",
            )
        ),
        "social draft contains no materialized language",
    )

    return normalized


def build_social_artifact_draft(
    *,
    request: dict[str, Any],
    package: dict[str, Any],
    artifacts: Iterable[Any],
    copy: dict[str, Any],
) -> dict[str, Any]:
    request = validate_materialization_request(
        request,
        package=package,
        artifacts=artifacts,
    )

    materialized_copy = normalize_copy(
        copy
    )

    identity_payload = {
        "request_digest": (
            request[
                "request_digest"
            ]
        ),
        "copy": (
            materialized_copy
        ),
    }

    draft = {
        "schema": (
            SOCIAL_ARTIFACT_DRAFT_VERSION
        ),
        "draft_id": (
            "social_draft_"
            + digest(
                identity_payload
            )[:24]
        ),
        "materialization_request_binding": {
            "request_id": (
                request[
                    "request_id"
                ]
            ),
            "request_digest": (
                request[
                    "request_digest"
                ]
            ),
        },
        "campaign_binding": (
            request[
                "campaign_binding"
            ]
        ),
        "slot_binding": (
            request[
                "slot_binding"
            ]
        ),
        "allowed_truth_bindings": (
            request[
                "allowed_truth_bindings"
            ]
        ),
        "copy": (
            materialized_copy
        ),
        "review_state": (
            "ATOMIC_REVIEW_REQUIRED"
        ),
        "visual_state": (
            "NOT_ATTACHED"
        ),
        "authority_state": (
            "DRAFT_ONLY"
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

    draft[
        "draft_digest"
    ] = digest(
        draft
    )

    return draft


def validate_social_artifact_draft(
    draft: Any,
    *,
    request: dict[str, Any],
    package: dict[str, Any],
    artifacts: Iterable[Any],
) -> dict[str, Any]:
    request = validate_materialization_request(
        request,
        package=package,
        artifacts=artifacts,
    )

    require(
        isinstance(
            draft,
            dict,
        ),
        "social artifact draft invalid",
    )

    expected_fields = {
        "schema",
        "draft_id",
        "materialization_request_binding",
        "campaign_binding",
        "slot_binding",
        "allowed_truth_bindings",
        "copy",
        "review_state",
        "visual_state",
        "authority_state",
        "factual_authority",
        "human_approval",
        "publication_authority",
        "draft_digest",
    }

    require(
        set(
            draft
        )
        == expected_fields,
        "social artifact draft fields invalid",
    )

    require(
        draft[
            "schema"
        ]
        == SOCIAL_ARTIFACT_DRAFT_VERSION,
        "social artifact draft schema invalid",
    )

    verify_bound_digest(
        draft,
        "draft_digest",
        "social artifact draft digest invalid",
    )

    require(
        draft[
            "materialization_request_binding"
        ]
        == {
            "request_id": (
                request[
                    "request_id"
                ]
            ),
            "request_digest": (
                request[
                    "request_digest"
                ]
            ),
        },
        "social draft materialization request binding invalid",
    )

    require(
        draft[
            "campaign_binding"
        ]
        == request[
            "campaign_binding"
        ],
        "social draft campaign binding invalid",
    )

    require(
        draft[
            "slot_binding"
        ]
        == request[
            "slot_binding"
        ],
        "social draft slot binding invalid",
    )

    require(
        draft[
            "allowed_truth_bindings"
        ]
        == request[
            "allowed_truth_bindings"
        ],
        "social draft truth binding invalid",
    )

    copy = normalize_copy(
        draft[
            "copy"
        ]
    )

    identity_payload = {
        "request_digest": (
            request[
                "request_digest"
            ]
        ),
        "copy": (
            copy
        ),
    }

    expected_draft_id = (
        "social_draft_"
        + digest(
            identity_payload
        )[:24]
    )

    require(
        draft[
            "draft_id"
        ]
        == expected_draft_id,
        "social draft deterministic identity invalid",
    )

    require(
        draft[
            "review_state"
        ]
        == "ATOMIC_REVIEW_REQUIRED",
        "social draft may not self-assert factual review",
    )

    require(
        draft[
            "visual_state"
        ]
        == "NOT_ATTACHED",
        "social draft may not self-assert visual completion",
    )

    require(
        draft[
            "authority_state"
        ]
        == "DRAFT_ONLY",
        "social draft authority invalid",
    )

    require(
        draft[
            "factual_authority"
        ]
        == "NONE",
        "social draft factual authority forbidden",
    )

    require(
        draft[
            "human_approval"
        ]
        == "NONE",
        "social draft human approval forbidden",
    )

    require(
        draft[
            "publication_authority"
        ]
        == "NONE",
        "social draft publication authority forbidden",
    )

    return dict(
        draft
    )
