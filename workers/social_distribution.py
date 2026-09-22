"""Governed social distribution planning for AnarchI Editorial Foundry.

This module creates planning artifacts only.

It may propose:
- channel,
- format,
- cadence,
- hook posture,
- caption posture,
- CTA posture,
- visual purpose,
- reviewed claim bindings.

It may not:
- write final social copy,
- invent factual claims,
- modify reviewed claims,
- approve content,
- grant publication authority,
- execute publication.

The past becomes evidence.
The present becomes execution.
The future remains proposal.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import re
from typing import Any, Iterable

from editorial_review_artifact import (
    validate_artifact,
)


WEEKLY_PACKAGE_VERSION = (
    "anarchi.weekly-campaign-package-proposal.v1"
)

CAMPAIGN_HORIZON_VERSION = (
    "anarchi.social-distribution-horizon.v1"
)

SOCIAL_DISTRIBUTION_EXPERT_VERSION = (
    "anarchi.social-distribution-expert.v1"
)

_HEX64 = re.compile(
    r"^[0-9a-f]{64}$"
)


_PLATFORM_FORMATS = {
    "FACEBOOK": {
        "POST",
        "CAROUSEL",
        "STORY",
        "REEL",
    },
    "INSTAGRAM": {
        "POST",
        "CAROUSEL",
        "STORY",
        "REEL",
    },
    "TIKTOK": {
        "SHORT_VIDEO",
    },
    "LINKEDIN": {
        "POST",
        "CAROUSEL",
        "ARTICLE_TEASER",
    },
    "X": {
        "POST",
        "THREAD",
    },
    "YOUTUBE": {
        "SHORT",
    },
}


_CONTENT_ROLES = {
    "EDUCATIONAL",
    "PROOF",
    "CONVERSION",
    "ENGAGEMENT",
    "AWARENESS",
}


_HOOK_POSTURES = {
    "PROBLEM_FIRST",
    "INSIGHT_FIRST",
    "PROOF_FIRST",
    "QUESTION_FIRST",
    "STORY_FIRST",
}


_CAPTION_POSTURES = {
    "CONCISE_EDUCATIONAL",
    "STANDARD_EDUCATIONAL",
    "NARRATIVE",
    "DIRECT_RESPONSE",
    "COMMUNITY",
}


_CTA_POSTURES = {
    "NONE",
    "SOFT",
    "LEARN_MORE",
    "VISIT",
    "COMMENT",
    "SAVE_SHARE",
}


_VISUAL_PURPOSES = {
    "DECORATIVE",
    "CONCEPTUAL",
    "EXPLANATORY",
    "FACTUAL",
}


class SocialDistributionFailure(
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
        raise SocialDistributionFailure(
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


def parse_day(
    value: str,
) -> date:
    require(
        isinstance(
            value,
            str,
        ),
        "date representation invalid",
    )

    try:
        return date.fromisoformat(
            value
        )
    except ValueError as exc:
        raise SocialDistributionFailure(
            "date representation invalid"
        ) from exc


def parse_timestamp(
    value: str,
) -> datetime:
    require(
        isinstance(
            value,
            str,
        ),
        "scheduled timestamp invalid",
    )

    try:
        observed = datetime.fromisoformat(
            value
        )
    except ValueError as exc:
        raise SocialDistributionFailure(
            "scheduled timestamp invalid"
        ) from exc

    require(
        observed.tzinfo
        is not None,
        "scheduled timestamp must be offset-aware",
    )

    require(
        observed.utcoffset()
        is not None,
        "scheduled timestamp must be offset-aware",
    )

    return observed


def expected_resolution(
    week_index: int,
) -> str:
    require(
        isinstance(
            week_index,
            int,
        )
        and not isinstance(
            week_index,
            bool,
        )
        and 1 <= week_index <= 8,
        "week index outside eight-week horizon",
    )

    if week_index == 1:
        return "READY_FOR_ADJUDICATION"

    if week_index <= 3:
        return "MATERIALIZATION_READY"

    return "STRUCTURED_INTENT"


def artifact_binding(
    artifact: Any,
) -> dict[str, Any]:
    try:
        validate_artifact(
            artifact
        )
    except Exception as exc:
        raise SocialDistributionFailure(
            "reviewed article artifact invalid"
        ) from exc

    artifact_digest = (
        artifact.artifact_digest
    )

    article_digest = (
        artifact.article_digest
    )

    material_claim_ids = list(
        artifact.material_claim_ids
    )

    require(
        isinstance(
            artifact_digest,
            str,
        )
        and _HEX64.fullmatch(
            artifact_digest
        )
        is not None,
        "reviewed artifact digest invalid",
    )

    require(
        isinstance(
            article_digest,
            str,
        )
        and _HEX64.fullmatch(
            article_digest
        )
        is not None,
        "reviewed article digest invalid",
    )

    require(
        len(
            material_claim_ids
        )
        == len(
            set(
                material_claim_ids
            )
        ),
        "duplicate material claim identity",
    )

    return {
        "reviewed_article_schema": (
            "anarchi.reviewed-article.v1"
        ),
        "artifact_digest": (
            artifact_digest
        ),
        "article_digest": (
            article_digest
        ),
        "material_claim_ids": sorted(
            material_claim_ids
        ),
    }


def normalize_sources(
    artifacts: Iterable[Any],
) -> tuple[
    list[dict[str, Any]],
    dict[str, set[str]],
]:
    bindings = [
        artifact_binding(
            artifact
        )
        for artifact in artifacts
    ]

    require(
        bool(
            bindings
        ),
        "weekly package requires reviewed sources",
    )

    digests = [
        binding[
            "artifact_digest"
        ]
        for binding in bindings
    ]

    require(
        len(
            digests
        )
        == len(
            set(
                digests
            )
        ),
        "duplicate reviewed source artifact",
    )

    bindings.sort(
        key=lambda item: item[
            "artifact_digest"
        ]
    )

    source_claims = {
        binding[
            "artifact_digest"
        ]: set(
            binding[
                "material_claim_ids"
            ]
        )
        for binding in bindings
    }

    return (
        bindings,
        source_claims,
    )


def normalize_claim_bindings(
    value: Any,
    source_claims: dict[str, set[str]],
) -> list[dict[str, Any]]:
    require(
        isinstance(
            value,
            list,
        )
        and bool(
            value
        ),
        "social slot requires reviewed claim bindings",
    )

    normalized: list[
        dict[str, Any]
    ] = []

    observed_artifacts: set[str] = set()

    for binding in value:
        require(
            isinstance(
                binding,
                dict,
            )
            and set(
                binding
            )
            == {
                "artifact_digest",
                "claim_ids",
            },
            "social claim binding fields invalid",
        )

        artifact_digest = binding[
            "artifact_digest"
        ]

        require(
            artifact_digest
            in source_claims,
            "social claim binding references unknown reviewed artifact",
        )

        require(
            artifact_digest
            not in observed_artifacts,
            "duplicate artifact in social claim bindings",
        )

        observed_artifacts.add(
            artifact_digest
        )

        claim_ids = binding[
            "claim_ids"
        ]

        require(
            isinstance(
                claim_ids,
                list,
            )
            and bool(
                claim_ids
            ),
            "social claim binding requires claim IDs",
        )

        require(
            all(
                isinstance(
                    claim_id,
                    str,
                )
                and bool(
                    claim_id
                )
                for claim_id in claim_ids
            ),
            "social claim identity invalid",
        )

        require(
            len(
                claim_ids
            )
            == len(
                set(
                    claim_ids
                )
            ),
            "duplicate social claim identity",
        )

        require(
            set(
                claim_ids
            ).issubset(
                source_claims[
                    artifact_digest
                ]
            ),
            "social slot may bind only reviewed material claims",
        )

        normalized.append(
            {
                "artifact_digest": (
                    artifact_digest
                ),
                "claim_ids": sorted(
                    claim_ids
                ),
            }
        )

    normalized.sort(
        key=lambda item: item[
            "artifact_digest"
        ]
    )

    return normalized


def normalize_slot(
    raw: Any,
    *,
    campaign_id: str,
    week_index: int,
    window_start: date,
    window_end: date,
    source_claims: dict[str, set[str]],
) -> dict[str, Any]:
    require(
        isinstance(
            raw,
            dict,
        ),
        "social distribution slot invalid",
    )

    expected_input = {
        "scheduled_at",
        "platform",
        "format",
        "platform_profile_version",
        "platform_profile_digest",
        "content_role",
        "hook_posture",
        "caption_posture",
        "cta_posture",
        "visual_purpose",
        "claim_bindings",
    }

    require(
        set(
            raw
        )
        == expected_input,
        "social distribution slot fields invalid",
    )

    scheduled = parse_timestamp(
        raw[
            "scheduled_at"
        ]
    )

    require(
        window_start
        <= scheduled.date()
        <= window_end,
        "social slot scheduled outside weekly package window",
    )

    platform = raw[
        "platform"
    ]

    format_name = raw[
        "format"
    ]

    require(
        platform
        in _PLATFORM_FORMATS,
        "social platform unsupported",
    )

    require(
        format_name
        in _PLATFORM_FORMATS[
            platform
        ],
        "social format unsupported for platform",
    )

    profile_version = raw[
        "platform_profile_version"
    ]

    profile_digest = raw[
        "platform_profile_digest"
    ]

    require(
        isinstance(
            profile_version,
            int,
        )
        and not isinstance(
            profile_version,
            bool,
        )
        and profile_version >= 1,
        "platform profile version invalid",
    )

    require(
        isinstance(
            profile_digest,
            str,
        )
        and _HEX64.fullmatch(
            profile_digest
        )
        is not None,
        "platform profile digest invalid",
    )

    require(
        raw[
            "content_role"
        ]
        in _CONTENT_ROLES,
        "social content role invalid",
    )

    require(
        raw[
            "hook_posture"
        ]
        in _HOOK_POSTURES,
        "social hook posture invalid",
    )

    require(
        raw[
            "caption_posture"
        ]
        in _CAPTION_POSTURES,
        "social caption posture invalid",
    )

    require(
        raw[
            "cta_posture"
        ]
        in _CTA_POSTURES,
        "social CTA posture invalid",
    )

    require(
        raw[
            "visual_purpose"
        ]
        in _VISUAL_PURPOSES,
        "social visual purpose invalid",
    )

    claim_bindings = (
        normalize_claim_bindings(
            raw[
                "claim_bindings"
            ],
            source_claims,
        )
    )

    identity_payload = {
        "campaign_id": (
            campaign_id
        ),
        "week_index": (
            week_index
        ),
        "scheduled_at": (
            raw[
                "scheduled_at"
            ]
        ),
        "platform": (
            platform
        ),
        "format": (
            format_name
        ),
        "claim_bindings": (
            claim_bindings
        ),
    }

    slot_id = (
        "social_slot_"
        + digest(
            identity_payload
        )[:24]
    )

    return {
        "slot_id": (
            slot_id
        ),
        "scheduled_at": (
            raw[
                "scheduled_at"
            ]
        ),
        "platform": (
            platform
        ),
        "format": (
            format_name
        ),
        "platform_profile": {
            "version": (
                profile_version
            ),
            "digest": (
                profile_digest
            ),
        },
        "content_role": (
            raw[
                "content_role"
            ]
        ),
        "hook_posture": (
            raw[
                "hook_posture"
            ]
        ),
        "caption_posture": (
            raw[
                "caption_posture"
            ]
        ),
        "cta_posture": (
            raw[
                "cta_posture"
            ]
        ),
        "visual_purpose": (
            raw[
                "visual_purpose"
            ]
        ),
        "claim_bindings": (
            claim_bindings
        ),
    }


def build_weekly_package(
    *,
    artifacts: Iterable[Any],
    campaign_id: str,
    campaign_objective: str,
    audience_segment: str,
    week_index: int,
    window_start: str,
    slots: list[dict[str, Any]],
    revision: int = 1,
    supersedes_package_digest: str | None = None,
) -> dict[str, Any]:
    require(
        isinstance(
            campaign_id,
            str,
        )
        and bool(
            campaign_id.strip()
        ),
        "campaign ID invalid",
    )

    require(
        isinstance(
            campaign_objective,
            str,
        )
        and bool(
            campaign_objective.strip()
        ),
        "campaign objective invalid",
    )

    require(
        isinstance(
            audience_segment,
            str,
        )
        and bool(
            audience_segment.strip()
        ),
        "audience segment invalid",
    )

    require(
        isinstance(
            revision,
            int,
        )
        and not isinstance(
            revision,
            bool,
        )
        and revision >= 1,
        "weekly package revision invalid",
    )

    if revision == 1:
        require(
            supersedes_package_digest
            is None,
            "initial package may not supersede another package",
        )

    if revision > 1:
        require(
            isinstance(
                supersedes_package_digest,
                str,
            )
            and _HEX64.fullmatch(
                supersedes_package_digest
            )
            is not None,
            "revised package must bind superseded package digest",
        )

    start = parse_day(
        window_start
    )

    end = (
        start
        + timedelta(
            days=6
        )
    )

    resolution = (
        expected_resolution(
            week_index
        )
    )

    source_bindings, source_claims = (
        normalize_sources(
            artifacts
        )
    )

    require(
        isinstance(
            slots,
            list,
        )
        and bool(
            slots
        ),
        "weekly package requires social slots",
    )

    require(
        len(
            slots
        )
        <= 28,
        "weekly package slot ceiling exceeded",
    )

    normalized_slots = [
        normalize_slot(
            slot,
            campaign_id=campaign_id,
            week_index=week_index,
            window_start=start,
            window_end=end,
            source_claims=source_claims,
        )
        for slot in slots
    ]

    slot_ids = [
        slot[
            "slot_id"
        ]
        for slot in normalized_slots
    ]

    require(
        len(
            slot_ids
        )
        == len(
            set(
                slot_ids
            )
        ),
        "duplicate deterministic social slot",
    )

    normalized_slots.sort(
        key=lambda item: (
            item[
                "scheduled_at"
            ],
            item[
                "platform"
            ],
            item[
                "slot_id"
            ],
        )
    )

    package_identity = {
        "campaign_id": (
            campaign_id
        ),
        "week_index": (
            week_index
        ),
        "window_start": (
            start.isoformat()
        ),
        "revision": (
            revision
        ),
        "supersedes_package_digest": (
            supersedes_package_digest
        ),
    }

    package = {
        "schema": (
            WEEKLY_PACKAGE_VERSION
        ),
        "package_id": (
            "campaign_week_"
            + digest(
                package_identity
            )[:24]
        ),
        "campaign_id": (
            campaign_id
        ),
        "campaign_objective": (
            campaign_objective
        ),
        "audience_segment": (
            audience_segment
        ),
        "week_index": (
            week_index
        ),
        "window_start": (
            start.isoformat()
        ),
        "window_end": (
            end.isoformat()
        ),
        "planning_resolution": (
            resolution
        ),
        "revision": (
            revision
        ),
        "supersedes_package_digest": (
            supersedes_package_digest
        ),
        "source_review_bindings": (
            source_bindings
        ),
        "distribution_slots": (
            normalized_slots
        ),
        "authority_state": (
            "PACKAGE_PROPOSAL_ONLY"
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

    package[
        "package_digest"
    ] = digest(
        package
    )

    return package


def validate_weekly_package(
    package: Any,
    *,
    artifacts: Iterable[Any],
) -> dict[str, Any]:
    require(
        isinstance(
            package,
            dict,
        ),
        "weekly package invalid",
    )

    expected_fields = {
        "schema",
        "package_id",
        "campaign_id",
        "campaign_objective",
        "audience_segment",
        "week_index",
        "window_start",
        "window_end",
        "planning_resolution",
        "revision",
        "supersedes_package_digest",
        "source_review_bindings",
        "distribution_slots",
        "authority_state",
        "factual_authority",
        "human_approval",
        "publication_authority",
        "package_digest",
    }

    require(
        set(
            package
        )
        == expected_fields,
        "weekly package fields invalid",
    )

    require(
        package[
            "schema"
        ]
        == WEEKLY_PACKAGE_VERSION,
        "weekly package schema invalid",
    )

    verify_bound_digest(
        package,
        "package_digest",
        "weekly package digest invalid",
    )

    start = parse_day(
        package[
            "window_start"
        ]
    )

    end = parse_day(
        package[
            "window_end"
        ]
    )

    require(
        end
        == start
        + timedelta(
            days=6
        ),
        "weekly package must cover exactly seven calendar days",
    )

    require(
        package[
            "planning_resolution"
        ]
        == expected_resolution(
            package[
                "week_index"
            ]
        ),
        "weekly planning resolution invalid",
    )

    revision = package[
        "revision"
    ]

    require(
        isinstance(
            revision,
            int,
        )
        and not isinstance(
            revision,
            bool,
        )
        and revision >= 1,
        "weekly package revision invalid",
    )

    supersedes = package[
        "supersedes_package_digest"
    ]

    if revision == 1:
        require(
            supersedes
            is None,
            "initial package supersedes another package",
        )

    if revision > 1:
        require(
            isinstance(
                supersedes,
                str,
            )
            and _HEX64.fullmatch(
                supersedes
            )
            is not None,
            "revised package supersedes digest invalid",
        )

        require(
            supersedes
            != package[
                "package_digest"
            ],
            "package may not supersede itself",
        )

    expected_sources, source_claims = (
        normalize_sources(
            artifacts
        )
    )

    require(
        package[
            "source_review_bindings"
        ]
        == expected_sources,
        "weekly package reviewed-source binding mismatch",
    )

    package_identity = {
        "campaign_id": (
            package[
                "campaign_id"
            ]
        ),
        "week_index": (
            package[
                "week_index"
            ]
        ),
        "window_start": (
            package[
                "window_start"
            ]
        ),
        "revision": (
            package[
                "revision"
            ]
        ),
        "supersedes_package_digest": (
            package[
                "supersedes_package_digest"
            ]
        ),
    }

    expected_package_id = (
        "campaign_week_"
        + digest(
            package_identity
        )[:24]
    )

    require(
        package[
            "package_id"
        ]
        == expected_package_id,
        "weekly package deterministic identity invalid",
    )

    slots = package[
        "distribution_slots"
    ]

    require(
        isinstance(
            slots,
            list,
        )
        and bool(
            slots
        ),
        "weekly package slots invalid",
    )

    observed_slot_ids: list[str] = []

    slot_fields = {
        "slot_id",
        "scheduled_at",
        "platform",
        "format",
        "platform_profile",
        "content_role",
        "hook_posture",
        "caption_posture",
        "cta_posture",
        "visual_purpose",
        "claim_bindings",
    }

    for slot in slots:
        require(
            isinstance(
                slot,
                dict,
            )
            and set(
                slot
            )
            == slot_fields,
            "materialized social slot fields invalid",
        )

        scheduled = parse_timestamp(
            slot[
                "scheduled_at"
            ]
        )

        require(
            start
            <= scheduled.date()
            <= end,
            "materialized social slot outside weekly window",
        )

        platform = slot[
            "platform"
        ]

        require(
            platform
            in _PLATFORM_FORMATS,
            "materialized social platform invalid",
        )

        require(
            slot[
                "format"
            ]
            in _PLATFORM_FORMATS[
                platform
            ],
            "materialized social format invalid",
        )

        profile = slot[
            "platform_profile"
        ]

        require(
            isinstance(
                profile,
                dict,
            )
            and set(
                profile
            )
            == {
                "version",
                "digest",
            },
            "platform profile binding invalid",
        )

        require(
            isinstance(
                profile[
                    "version"
                ],
                int,
            )
            and not isinstance(
                profile[
                    "version"
                ],
                bool,
            )
            and profile[
                "version"
            ] >= 1,
            "platform profile version invalid",
        )

        require(
            isinstance(
                profile[
                    "digest"
                ],
                str,
            )
            and _HEX64.fullmatch(
                profile[
                    "digest"
                ]
            )
            is not None,
            "platform profile digest invalid",
        )

        require(
            slot[
                "content_role"
            ]
            in _CONTENT_ROLES,
            "content role invalid",
        )

        require(
            slot[
                "hook_posture"
            ]
            in _HOOK_POSTURES,
            "hook posture invalid",
        )

        require(
            slot[
                "caption_posture"
            ]
            in _CAPTION_POSTURES,
            "caption posture invalid",
        )

        require(
            slot[
                "cta_posture"
            ]
            in _CTA_POSTURES,
            "CTA posture invalid",
        )

        require(
            slot[
                "visual_purpose"
            ]
            in _VISUAL_PURPOSES,
            "visual purpose invalid",
        )

        normalized_claims = normalize_claim_bindings(
            slot[
                "claim_bindings"
            ],
            source_claims,
        )

        slot_identity_payload = {
            "campaign_id": (
                package[
                    "campaign_id"
                ]
            ),
            "week_index": (
                package[
                    "week_index"
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
            "claim_bindings": (
                normalized_claims
            ),
        }

        expected_slot_id = (
            "social_slot_"
            + digest(
                slot_identity_payload
            )[:24]
        )

        require(
            slot[
                "slot_id"
            ]
            == expected_slot_id,
            "social slot deterministic identity invalid",
        )

        observed_slot_ids.append(
            slot[
                "slot_id"
            ]
        )

    require(
        len(
            observed_slot_ids
        )
        == len(
            set(
                observed_slot_ids
            )
        ),
        "duplicate slot identity",
    )

    expected_slot_order = sorted(
        slots,
        key=lambda item: (
            item[
                "scheduled_at"
            ],
            item[
                "platform"
            ],
            item[
                "slot_id"
            ],
        ),
    )

    require(
        slots
        == expected_slot_order,
        "weekly package slot order is not canonical",
    )

    require(
        package[
            "authority_state"
        ]
        == "PACKAGE_PROPOSAL_ONLY",
        "weekly package authority invalid",
    )

    require(
        package[
            "factual_authority"
        ]
        == "NONE",
        "weekly package factual authority forbidden",
    )

    require(
        package[
            "human_approval"
        ]
        == "NONE",
        "weekly package human approval forbidden",
    )

    require(
        package[
            "publication_authority"
        ]
        == "NONE",
        "weekly package publication authority forbidden",
    )

    return dict(
        package
    )


def validate_package_envelope(
    package: Any,
) -> dict[str, Any]:
    require(
        isinstance(
            package,
            dict,
        ),
        "campaign horizon package invalid",
    )

    expected_fields = {
        "schema",
        "package_id",
        "campaign_id",
        "campaign_objective",
        "audience_segment",
        "week_index",
        "window_start",
        "window_end",
        "planning_resolution",
        "revision",
        "supersedes_package_digest",
        "source_review_bindings",
        "distribution_slots",
        "authority_state",
        "factual_authority",
        "human_approval",
        "publication_authority",
        "package_digest",
    }

    require(
        set(
            package
        )
        == expected_fields,
        "campaign horizon package fields invalid",
    )

    require(
        package[
            "schema"
        ]
        == WEEKLY_PACKAGE_VERSION,
        "campaign horizon package schema invalid",
    )

    verify_bound_digest(
        package,
        "package_digest",
        "campaign horizon package digest invalid",
    )

    start = parse_day(
        package[
            "window_start"
        ]
    )

    end = parse_day(
        package[
            "window_end"
        ]
    )

    require(
        end
        == start
        + timedelta(
            days=6
        ),
        "campaign horizon package window invalid",
    )

    require(
        package[
            "planning_resolution"
        ]
        == expected_resolution(
            package[
                "week_index"
            ]
        ),
        "campaign horizon package resolution invalid",
    )

    revision = package[
        "revision"
    ]

    require(
        isinstance(
            revision,
            int,
        )
        and not isinstance(
            revision,
            bool,
        )
        and revision >= 1,
        "campaign horizon package revision invalid",
    )

    supersedes = package[
        "supersedes_package_digest"
    ]

    if revision == 1:
        require(
            supersedes
            is None,
            "campaign horizon initial package supersedes another package",
        )

    if revision > 1:
        require(
            isinstance(
                supersedes,
                str,
            )
            and _HEX64.fullmatch(
                supersedes
            )
            is not None,
            "campaign horizon revised package supersedes digest invalid",
        )

    package_identity = {
        "campaign_id": (
            package[
                "campaign_id"
            ]
        ),
        "week_index": (
            package[
                "week_index"
            ]
        ),
        "window_start": (
            package[
                "window_start"
            ]
        ),
        "revision": (
            revision
        ),
        "supersedes_package_digest": (
            supersedes
        ),
    }

    expected_package_id = (
        "campaign_week_"
        + digest(
            package_identity
        )[:24]
    )

    require(
        package[
            "package_id"
        ]
        == expected_package_id,
        "campaign horizon package deterministic identity invalid",
    )

    source_bindings = package[
        "source_review_bindings"
    ]

    require(
        isinstance(
            source_bindings,
            list,
        )
        and bool(
            source_bindings
        ),
        "campaign horizon reviewed source bindings invalid",
    )

    source_claims: dict[
        str,
        set[str]
    ] = {}

    observed_sources: list[str] = []

    for binding in source_bindings:
        require(
            isinstance(
                binding,
                dict,
            )
            and set(
                binding
            )
            == {
                "reviewed_article_schema",
                "artifact_digest",
                "article_digest",
                "material_claim_ids",
            },
            "campaign horizon reviewed source binding fields invalid",
        )

        require(
            binding[
                "reviewed_article_schema"
            ]
            == "anarchi.reviewed-article.v1",
            "campaign horizon reviewed source schema invalid",
        )

        artifact_digest = binding[
            "artifact_digest"
        ]

        article_digest = binding[
            "article_digest"
        ]

        require(
            isinstance(
                artifact_digest,
                str,
            )
            and _HEX64.fullmatch(
                artifact_digest
            )
            is not None,
            "campaign horizon artifact digest invalid",
        )

        require(
            isinstance(
                article_digest,
                str,
            )
            and _HEX64.fullmatch(
                article_digest
            )
            is not None,
            "campaign horizon article digest invalid",
        )

        claim_ids = binding[
            "material_claim_ids"
        ]

        require(
            isinstance(
                claim_ids,
                list,
            ),
            "campaign horizon material claim IDs invalid",
        )

        require(
            all(
                isinstance(
                    claim_id,
                    str,
                )
                and bool(
                    claim_id
                )
                for claim_id in claim_ids
            ),
            "campaign horizon material claim identity invalid",
        )

        require(
            len(
                claim_ids
            )
            == len(
                set(
                    claim_ids
                )
            ),
            "campaign horizon duplicate material claim identity",
        )

        observed_sources.append(
            artifact_digest
        )

        source_claims[
            artifact_digest
        ] = set(
            claim_ids
        )

    require(
        observed_sources
        == sorted(
            observed_sources
        ),
        "campaign horizon reviewed sources are not canonical",
    )

    require(
        len(
            observed_sources
        )
        == len(
            set(
                observed_sources
            )
        ),
        "campaign horizon duplicate reviewed source",
    )

    slots = package[
        "distribution_slots"
    ]

    require(
        isinstance(
            slots,
            list,
        )
        and bool(
            slots
        ),
        "campaign horizon slots invalid",
    )

    slot_fields = {
        "slot_id",
        "scheduled_at",
        "platform",
        "format",
        "platform_profile",
        "content_role",
        "hook_posture",
        "caption_posture",
        "cta_posture",
        "visual_purpose",
        "claim_bindings",
    }

    observed_slot_ids: list[str] = []

    for slot in slots:
        require(
            isinstance(
                slot,
                dict,
            )
            and set(
                slot
            )
            == slot_fields,
            "campaign horizon slot fields invalid",
        )

        scheduled = parse_timestamp(
            slot[
                "scheduled_at"
            ]
        )

        require(
            start
            <= scheduled.date()
            <= end,
            "campaign horizon slot outside package window",
        )

        platform = slot[
            "platform"
        ]

        require(
            platform
            in _PLATFORM_FORMATS,
            "campaign horizon platform invalid",
        )

        require(
            slot[
                "format"
            ]
            in _PLATFORM_FORMATS[
                platform
            ],
            "campaign horizon format invalid",
        )

        profile = slot[
            "platform_profile"
        ]

        require(
            isinstance(
                profile,
                dict,
            )
            and set(
                profile
            )
            == {
                "version",
                "digest",
            },
            "campaign horizon platform profile invalid",
        )

        require(
            isinstance(
                profile[
                    "version"
                ],
                int,
            )
            and not isinstance(
                profile[
                    "version"
                ],
                bool,
            )
            and profile[
                "version"
            ] >= 1,
            "campaign horizon profile version invalid",
        )

        require(
            isinstance(
                profile[
                    "digest"
                ],
                str,
            )
            and _HEX64.fullmatch(
                profile[
                    "digest"
                ]
            )
            is not None,
            "campaign horizon profile digest invalid",
        )

        require(
            slot[
                "content_role"
            ]
            in _CONTENT_ROLES,
            "campaign horizon content role invalid",
        )

        require(
            slot[
                "hook_posture"
            ]
            in _HOOK_POSTURES,
            "campaign horizon hook posture invalid",
        )

        require(
            slot[
                "caption_posture"
            ]
            in _CAPTION_POSTURES,
            "campaign horizon caption posture invalid",
        )

        require(
            slot[
                "cta_posture"
            ]
            in _CTA_POSTURES,
            "campaign horizon CTA posture invalid",
        )

        require(
            slot[
                "visual_purpose"
            ]
            in _VISUAL_PURPOSES,
            "campaign horizon visual purpose invalid",
        )

        normalized_claims = normalize_claim_bindings(
            slot[
                "claim_bindings"
            ],
            source_claims,
        )

        slot_identity_payload = {
            "campaign_id": (
                package[
                    "campaign_id"
                ]
            ),
            "week_index": (
                package[
                    "week_index"
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
            "claim_bindings": (
                normalized_claims
            ),
        }

        expected_slot_id = (
            "social_slot_"
            + digest(
                slot_identity_payload
            )[:24]
        )

        require(
            slot[
                "slot_id"
            ]
            == expected_slot_id,
            "campaign horizon slot deterministic identity invalid",
        )

        observed_slot_ids.append(
            slot[
                "slot_id"
            ]
        )

    require(
        len(
            observed_slot_ids
        )
        == len(
            set(
                observed_slot_ids
            )
        ),
        "campaign horizon duplicate slot identity",
    )

    require(
        slots
        == sorted(
            slots,
            key=lambda item: (
                item[
                    "scheduled_at"
                ],
                item[
                    "platform"
                ],
                item[
                    "slot_id"
                ],
            ),
        ),
        "campaign horizon slot order is not canonical",
    )

    require(
        package[
            "authority_state"
        ]
        == "PACKAGE_PROPOSAL_ONLY",
        "campaign horizon package authority invalid",
    )

    require(
        package[
            "factual_authority"
        ]
        == "NONE",
        "campaign horizon factual authority forbidden",
    )

    require(
        package[
            "human_approval"
        ]
        == "NONE",
        "campaign horizon human approval forbidden",
    )

    require(
        package[
            "publication_authority"
        ]
        == "NONE",
        "campaign horizon publication authority forbidden",
    )

    return dict(
        package
    )


def build_campaign_horizon(
    packages: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    normalized = [
        validate_package_envelope(
            package
        )
        for package in packages
    ]

    require(
        len(
            normalized
        )
        == 8,
        "social distribution horizon requires exactly eight weekly packages",
    )

    normalized.sort(
        key=lambda item: item[
            "week_index"
        ]
    )

    expected_indices = list(
        range(
            1,
            9,
        )
    )

    observed_indices = [
        package[
            "week_index"
        ]
        for package in normalized
    ]

    require(
        observed_indices
        == expected_indices,
        "campaign horizon week indexes must be contiguous 1 through 8",
    )

    campaign_ids = {
        package[
            "campaign_id"
        ]
        for package in normalized
    }

    require(
        len(
            campaign_ids
        )
        == 1,
        "campaign horizon may contain only one campaign",
    )

    for previous, current in zip(
        normalized,
        normalized[1:],
    ):
        previous_end = parse_day(
            previous[
                "window_end"
            ]
        )

        current_start = parse_day(
            current[
                "window_start"
            ]
        )

        require(
            current_start
            == previous_end
            + timedelta(
                days=1
            ),
            "campaign horizon weekly windows must be contiguous",
        )

    package_digests = [
        package[
            "package_digest"
        ]
        for package in normalized
    ]

    require(
        len(
            package_digests
        )
        == len(
            set(
                package_digests
            )
        ),
        "campaign horizon contains duplicate package digest",
    )

    summaries = [
        {
            "week_index": (
                package[
                    "week_index"
                ]
            ),
            "package_id": (
                package[
                    "package_id"
                ]
            ),
            "window_start": (
                package[
                    "window_start"
                ]
            ),
            "window_end": (
                package[
                    "window_end"
                ]
            ),
            "planning_resolution": (
                package[
                    "planning_resolution"
                ]
            ),
            "revision": (
                package[
                    "revision"
                ]
            ),
            "supersedes_package_digest": (
                package[
                    "supersedes_package_digest"
                ]
            ),
            "package_digest": (
                package[
                    "package_digest"
                ]
            ),
        }
        for package in normalized
    ]

    campaign_id = normalized[
        0
    ][
        "campaign_id"
    ]

    horizon = {
        "schema": (
            CAMPAIGN_HORIZON_VERSION
        ),
        "expert_contract": (
            SOCIAL_DISTRIBUTION_EXPERT_VERSION
        ),
        "campaign_id": (
            campaign_id
        ),
        "horizon_weeks": 8,
        "packages": (
            summaries
        ),
        "planning_law": {
            "past": "EVIDENCE",
            "present": "EXECUTION_AFTER_AUTHORITY",
            "future": "PROPOSAL",
            "replanning": (
                "NEW_DIGEST_REQUIRES_FRESH_ADJUDICATION"
            ),
        },
        "authority_state": (
            "PLANNING_ONLY"
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

    horizon[
        "horizon_digest"
    ] = digest(
        horizon
    )

    return horizon


def validate_campaign_horizon(
    horizon: Any,
    *,
    packages: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    require(
        isinstance(
            horizon,
            dict,
        ),
        "campaign horizon invalid",
    )

    expected_fields = {
        "schema",
        "expert_contract",
        "campaign_id",
        "horizon_weeks",
        "packages",
        "planning_law",
        "authority_state",
        "factual_authority",
        "human_approval",
        "publication_authority",
        "horizon_digest",
    }

    require(
        set(
            horizon
        )
        == expected_fields,
        "campaign horizon fields invalid",
    )

    require(
        horizon[
            "schema"
        ]
        == CAMPAIGN_HORIZON_VERSION,
        "campaign horizon schema invalid",
    )

    require(
        horizon[
            "expert_contract"
        ]
        == SOCIAL_DISTRIBUTION_EXPERT_VERSION,
        "social distribution expert contract invalid",
    )

    verify_bound_digest(
        horizon,
        "horizon_digest",
        "campaign horizon digest invalid",
    )

    rebuilt = build_campaign_horizon(
        packages
    )

    require(
        horizon
        == rebuilt,
        "campaign horizon package binding mismatch",
    )

    require(
        horizon[
            "authority_state"
        ]
        == "PLANNING_ONLY",
        "campaign horizon authority invalid",
    )

    require(
        horizon[
            "factual_authority"
        ]
        == "NONE",
        "campaign horizon factual authority forbidden",
    )

    require(
        horizon[
            "human_approval"
        ]
        == "NONE",
        "campaign horizon human approval forbidden",
    )

    require(
        horizon[
            "publication_authority"
        ]
        == "NONE",
        "campaign horizon publication authority forbidden",
    )

    return dict(
        horizon
    )
