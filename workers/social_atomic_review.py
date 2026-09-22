"""Social Artifact Draft -> existing Atomic Reviewer bridge.

Laws:

- Planning is not review.
- Reviewed source material does not make derived wording reviewed.
- Source verdicts are never inherited.
- Only evidence actually relied on by an allowed reviewed source claim
  may enter the derived social review evidence pool.
- Candidate evidence is not support.
- Materialized social claims require fresh verification.
- Atomic Reviewer owns review-text identity semantics.
- Destination is operational metadata and is excluded from prose review.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable

from editorial_claims import (
    ClaimLedger,
    ExtractedClaim,
    article_digest,
    extract_claims,
)

from editorial_evidence import (
    ClaimEvidenceSet,
    EvidenceSource,
    bind_evidence_candidates,
)

from editorial_verifier import (
    ClaimVerification,
    build_article_verification,
)

from editorial_review_artifact import (
    ReviewProvenance,
    ReviewedArticleArtifact,
    build_reviewed_article_artifact,
    validate_artifact,
)

from social_artifact import (
    validate_social_artifact_draft,
)


SOCIAL_REVIEW_CASE_VERSION = (
    "anarchi.social-atomic-review-case.v1"
)

SOCIAL_REVIEWED_ARTIFACT_VERSION = (
    "anarchi.reviewed-social-artifact.v1"
)

PROJECTION_VERSION = (
    "anarchi.social-review-projection.v1"
)


class SocialAtomicReviewFailure(
    Exception
):
    pass


@dataclass(
    frozen=True
)
class ProjectionField:
    field_name: str
    text: str
    span_start: int
    span_end: int


@dataclass(
    frozen=True
)
class SocialReviewCase:
    schema_version: str
    projection_version: str
    draft_id: str
    draft_digest: str
    materialization_request_digest: str
    package_digest: str
    slot_id: str
    projection_text: str
    projection_digest: str
    projection_fields: tuple[
        ProjectionField,
        ...
    ]
    claim_ledger: ClaimLedger
    evidence_sets: tuple[
        ClaimEvidenceSet,
        ...
    ]
    source_review_artifact_digests: tuple[
        str,
        ...
    ]


@dataclass(
    frozen=True
)
class ReviewedSocialArtifact:
    schema_version: str
    draft_id: str
    draft_digest: str
    materialization_request_digest: str
    package_digest: str
    slot_id: str
    projection_version: str
    projection_text: str
    projection_digest: str
    projection_fields: tuple[
        ProjectionField,
        ...
    ]
    review_core: ReviewedArticleArtifact
    authority_state: str
    factual_authority: str
    human_approval: str
    publication_authority: str
    reviewed_social_digest: str


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise SocialAtomicReviewFailure(
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
                for name in item.__dataclass_fields__
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


def build_projection(
    draft: dict[str, Any],
) -> tuple[
    str,
    tuple[
        ProjectionField,
        ...
    ],
]:
    order = (
        (
            "headline",
            "HEADLINE",
        ),
        (
            "body",
            "BODY",
        ),
        (
            "cta",
            "CTA",
        ),
        (
            "alt_text",
            "ALT_TEXT",
        ),
    )

    parts: list[str] = []
    fields: list[
        ProjectionField
    ] = []

    cursor = 0

    for field_name, label in order:
        value = draft[
            "copy"
        ][
            field_name
        ]

        if value is None:
            continue

        if parts:
            separator = "\n\n"

            parts.append(
                separator
            )

            cursor += len(
                separator
            )

        prefix = (
            "# "
            + label
            + "\n\n"
        )

        parts.append(
            prefix
        )

        cursor += len(
            prefix
        )

        start = cursor

        parts.append(
            value
        )

        cursor += len(
            value
        )

        end = cursor

        fields.append(
            ProjectionField(
                field_name=field_name,
                text=value,
                span_start=start,
                span_end=end,
            )
        )

    require(
        bool(
            fields
        ),
        "social review projection contains no customer-facing language",
    )

    parts.append(
        "\n"
    )

    projection = "".join(
        parts
    )

    return (
        projection,
        tuple(
            fields
        ),
    )


def claim_field(
    claim: ExtractedClaim,
    fields: tuple[
        ProjectionField,
        ...
    ],
) -> str:
    owners = [
        field.field_name
        for field in fields
        if (
            claim.source_span_start
            >= field.span_start
            and claim.source_span_end
            <= field.span_end
        )
    ]

    require(
        len(
            owners
        )
        == 1,
        "social claim does not resolve to exactly one copy field",
    )

    return owners[
        0
    ]


def source_artifact_map(
    artifacts: Iterable[
        ReviewedArticleArtifact
    ],
) -> dict[
    str,
    ReviewedArticleArtifact
]:
    result: dict[
        str,
        ReviewedArticleArtifact
    ] = {}

    for artifact in artifacts:
        try:
            validate_artifact(
                artifact
            )
        except Exception as exc:
            raise SocialAtomicReviewFailure(
                "reviewed source artifact invalid"
            ) from exc

        require(
            artifact.text_review_passed,
            "source artifact text review not passed",
        )

        require(
            artifact.artifact_digest
            not in result,
            "duplicate source reviewed artifact",
        )

        result[
            artifact.artifact_digest
        ] = artifact

    require(
        bool(
            result
        ),
        "social review requires reviewed source artifacts",
    )

    return result


def relied_source_evidence(
    *,
    draft: dict[str, Any],
    artifacts: Iterable[
        ReviewedArticleArtifact
    ],
) -> tuple[
    EvidenceSource,
    ...
]:
    by_digest = source_artifact_map(
        artifacts
    )

    sources: dict[
        tuple[
            int,
            str,
            str,
        ],
        EvidenceSource,
    ] = {}

    for binding in draft[
        "allowed_truth_bindings"
    ]:
        artifact_digest_value = binding[
            "artifact_digest"
        ]

        require(
            artifact_digest_value
            in by_digest,
            "allowed truth source artifact absent",
        )

        artifact = by_digest[
            artifact_digest_value
        ]

        source_claims = {
            claim.claim_id: claim
            for claim
            in artifact.claim_ledger.claims
        }

        evidence_sets = {
            evidence_set.claim_id: evidence_set
            for evidence_set
            in artifact.evidence_sets
        }

        verifications = {
            verification.claim_id: verification
            for verification
            in artifact.article_verification.claims
        }

        for claim_id in binding[
            "claim_ids"
        ]:
            require(
                claim_id
                in source_claims,
                "allowed truth claim absent from source ledger",
            )

            source_claim = source_claims[
                claim_id
            ]

            require(
                source_claim.material,
                "allowed truth binding must reference material source claim",
            )

            require(
                claim_id
                in verifications,
                "source claim verification absent",
            )

            verification = verifications[
                claim_id
            ]

            require(
                verification.acceptable,
                "allowed source claim is not verification-acceptable",
            )

            require(
                claim_id
                in evidence_sets,
                "source evidence set absent",
            )

            candidates = {
                (
                    candidate.packet_id,
                    candidate.source_url,
                    candidate.excerpt_digest,
                ): candidate
                for candidate
                in evidence_sets[
                    claim_id
                ].candidates
            }

            for relied in verification.evidence:
                identity = (
                    relied.packet_id,
                    relied.source_url,
                    relied.excerpt_digest,
                )

                require(
                    identity
                    in candidates,
                    "relied evidence missing from source evidence set",
                )

                candidate = candidates[
                    identity
                ]

                require(
                    candidate.eligible,
                    "relied source evidence is not eligible",
                )

                sources[
                    identity
                ] = EvidenceSource(
                    packet_id=(
                        candidate.packet_id
                    ),
                    title=(
                        candidate.source_title
                    ),
                    url=(
                        candidate.source_url
                    ),
                    excerpt=(
                        candidate.excerpt
                    ),
                    provider=(
                        candidate.provider
                    ),
                    relevance_passed=True,
                )

    require(
        bool(
            sources
        ),
        "social review inherited no relied source evidence",
    )

    return tuple(
        sources[
            identity
        ]
        for identity in sorted(
            sources
        )
    )


def build_social_review_case(
    *,
    draft: dict[str, Any],
    request: dict[str, Any],
    package: dict[str, Any],
    artifacts: Iterable[
        ReviewedArticleArtifact
    ],
) -> SocialReviewCase:
    artifacts = tuple(
        artifacts
    )

    try:
        draft = validate_social_artifact_draft(
            draft,
            request=request,
            package=package,
            artifacts=artifacts,
        )
    except Exception as exc:
        raise SocialAtomicReviewFailure(
            "social draft ancestry validation failed"
        ) from exc

    require(
        draft[
            "review_state"
        ]
        == "ATOMIC_REVIEW_REQUIRED",
        "social draft review state invalid",
    )

    projection, fields = (
        build_projection(
            draft
        )
    )

    ledger = extract_claims(
        projection
    )

    expected_projection_digest = (
        article_digest(
            projection
        )
    )

    require(
        ledger.article_digest
        == expected_projection_digest,
        "Atomic Reviewer projection identity mismatch",
    )

    for claim in ledger.claims:
        claim_field(
            claim,
            fields,
        )

    sources = relied_source_evidence(
        draft=draft,
        artifacts=artifacts,
    )

    evidence_sets = tuple(
        bind_evidence_candidates(
            claim,
            sources,
        )
        for claim in ledger.claims
    )

    source_digests = tuple(
        sorted(
            {
                binding[
                    "artifact_digest"
                ]
                for binding
                in draft[
                    "allowed_truth_bindings"
                ]
            }
        )
    )

    return SocialReviewCase(
        schema_version=(
            SOCIAL_REVIEW_CASE_VERSION
        ),
        projection_version=(
            PROJECTION_VERSION
        ),
        draft_id=(
            draft[
                "draft_id"
            ]
        ),
        draft_digest=(
            draft[
                "draft_digest"
            ]
        ),
        materialization_request_digest=(
            request[
                "request_digest"
            ]
        ),
        package_digest=(
            package[
                "package_digest"
            ]
        ),
        slot_id=(
            request[
                "slot_binding"
            ][
                "slot_id"
            ]
        ),
        projection_text=(
            projection
        ),
        projection_digest=(
            expected_projection_digest
        ),
        projection_fields=(
            fields
        ),
        claim_ledger=(
            ledger
        ),
        evidence_sets=(
            evidence_sets
        ),
        source_review_artifact_digests=(
            source_digests
        ),
    )


def validate_social_review_case(
    case: SocialReviewCase,
) -> SocialReviewCase:
    require(
        isinstance(
            case,
            SocialReviewCase,
        ),
        "social review case invalid",
    )

    require(
        case.schema_version
        == SOCIAL_REVIEW_CASE_VERSION,
        "social review case schema invalid",
    )

    require(
        case.projection_version
        == PROJECTION_VERSION,
        "social projection version invalid",
    )

    require(
        case.projection_digest
        == article_digest(
            case.projection_text
        ),
        "social projection digest invalid",
    )

    rebuilt_ledger = extract_claims(
        case.projection_text
    )

    require(
        rebuilt_ledger
        == case.claim_ledger,
        "social review claim ledger not canonical",
    )

    require(
        rebuilt_ledger.article_digest
        == case.projection_digest,
        "social review ledger identity mismatch",
    )

    for claim in case.claim_ledger.claims:
        claim_field(
            claim,
            case.projection_fields,
        )

    require(
        len(
            case.source_review_artifact_digests
        )
        == len(
            set(
                case.source_review_artifact_digests
            )
        ),
        "duplicate source reviewed artifact digest",
    )

    return case


def build_reviewed_social_artifact(
    *,
    case: SocialReviewCase,
    claim_verifications: Iterable[
        ClaimVerification
    ],
    provenance: ReviewProvenance,
) -> ReviewedSocialArtifact:
    case = validate_social_review_case(
        case
    )

    verifications = tuple(
        claim_verifications
    )

    expected_material_claim_ids = tuple(
        claim.claim_id
        for claim
        in case.claim_ledger.claims
        if claim.material
    )

    article_verification = (
        build_article_verification(
            case.projection_digest,
            expected_material_claim_ids,
            verifications,
        )
    )

    require(
        article_verification.passed,
        "social atomic verification did not pass",
    )

    by_claim_id = {
        verification.claim_id: verification
        for verification
        in article_verification.claims
    }

    for claim in case.claim_ledger.claims:
        require(
            claim.claim_id
            in by_claim_id,
            "social claim verification missing",
        )

        verification = by_claim_id[
            claim.claim_id
        ]

        require(
            verification.claim_text
            == claim.text,
            "social verification claim text mismatch",
        )

        require(
            verification.claim_type
            == claim.claim_type,
            "social verification claim type mismatch",
        )

        require(
            verification.material
            == claim.material,
            "social verification materiality mismatch",
        )

    core = build_reviewed_article_artifact(
        article_text=(
            case.projection_text
        ),
        claim_ledger=(
            case.claim_ledger
        ),
        evidence_sets=(
            case.evidence_sets
        ),
        article_verification=(
            article_verification
        ),
        repair_history=(),
        provenance=(
            provenance
        ),
    )

    validate_artifact(
        core
    )

    require(
        core.article_digest
        == case.projection_digest,
        "reviewed core changed social projection identity",
    )

    payload = {
        "schema_version": (
            SOCIAL_REVIEWED_ARTIFACT_VERSION
        ),
        "draft_id": (
            case.draft_id
        ),
        "draft_digest": (
            case.draft_digest
        ),
        "materialization_request_digest": (
            case.materialization_request_digest
        ),
        "package_digest": (
            case.package_digest
        ),
        "slot_id": (
            case.slot_id
        ),
        "projection_version": (
            case.projection_version
        ),
        "projection_text": (
            case.projection_text
        ),
        "projection_digest": (
            case.projection_digest
        ),
        "projection_fields": (
            case.projection_fields
        ),
        "review_core_artifact_digest": (
            core.artifact_digest
        ),
        "authority_state": (
            "TEXT_REVIEWED_ONLY"
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

    reviewed_digest = digest(
        payload
    )

    return ReviewedSocialArtifact(
        schema_version=(
            SOCIAL_REVIEWED_ARTIFACT_VERSION
        ),
        draft_id=(
            case.draft_id
        ),
        draft_digest=(
            case.draft_digest
        ),
        materialization_request_digest=(
            case.materialization_request_digest
        ),
        package_digest=(
            case.package_digest
        ),
        slot_id=(
            case.slot_id
        ),
        projection_version=(
            case.projection_version
        ),
        projection_text=(
            case.projection_text
        ),
        projection_digest=(
            case.projection_digest
        ),
        projection_fields=(
            case.projection_fields
        ),
        review_core=(
            core
        ),
        authority_state=(
            "TEXT_REVIEWED_ONLY"
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
        reviewed_social_digest=(
            reviewed_digest
        ),
    )


def validate_reviewed_social_artifact(
    artifact: ReviewedSocialArtifact,
    *,
    draft: dict[str, Any],
    request: dict[str, Any],
    package: dict[str, Any],
    source_artifacts: Iterable[
        ReviewedArticleArtifact
    ],
) -> ReviewedSocialArtifact:
    require(
        isinstance(
            artifact,
            ReviewedSocialArtifact,
        ),
        "reviewed social artifact invalid",
    )

    require(
        artifact.schema_version
        == SOCIAL_REVIEWED_ARTIFACT_VERSION,
        "reviewed social artifact schema invalid",
    )

    source_artifacts = tuple(
        source_artifacts
    )

    expected_case = (
        build_social_review_case(
            draft=draft,
            request=request,
            package=package,
            artifacts=source_artifacts,
        )
    )

    require(
        artifact.draft_id
        == expected_case.draft_id,
        "reviewed social draft identity mismatch",
    )

    require(
        artifact.draft_digest
        == expected_case.draft_digest,
        "reviewed social draft digest mismatch",
    )

    require(
        artifact.materialization_request_digest
        == expected_case.materialization_request_digest,
        "reviewed social request ancestry mismatch",
    )

    require(
        artifact.package_digest
        == expected_case.package_digest,
        "reviewed social package ancestry mismatch",
    )

    require(
        artifact.slot_id
        == expected_case.slot_id,
        "reviewed social slot ancestry mismatch",
    )

    require(
        artifact.projection_version
        == expected_case.projection_version,
        "reviewed social projection version mismatch",
    )

    require(
        artifact.projection_text
        == expected_case.projection_text,
        "reviewed social projection text mismatch",
    )

    require(
        artifact.projection_digest
        == expected_case.projection_digest,
        "reviewed social projection identity mismatch",
    )

    require(
        artifact.projection_fields
        == expected_case.projection_fields,
        "reviewed social projection field ownership mismatch",
    )

    validate_artifact(
        artifact.review_core
    )

    require(
        artifact.review_core.text_review_passed,
        "reviewed social core text review not passed",
    )

    require(
        artifact.review_core.article_text
        == artifact.projection_text,
        "reviewed social projection/core text mismatch",
    )

    require(
        artifact.review_core.article_digest
        == artifact.projection_digest,
        "reviewed social projection/core digest mismatch",
    )

    payload = {
        "schema_version": (
            artifact.schema_version
        ),
        "draft_id": (
            artifact.draft_id
        ),
        "draft_digest": (
            artifact.draft_digest
        ),
        "materialization_request_digest": (
            artifact.materialization_request_digest
        ),
        "package_digest": (
            artifact.package_digest
        ),
        "slot_id": (
            artifact.slot_id
        ),
        "projection_version": (
            artifact.projection_version
        ),
        "projection_text": (
            artifact.projection_text
        ),
        "projection_digest": (
            artifact.projection_digest
        ),
        "projection_fields": (
            artifact.projection_fields
        ),
        "review_core_artifact_digest": (
            artifact.review_core.artifact_digest
        ),
        "authority_state": (
            artifact.authority_state
        ),
        "factual_authority": (
            artifact.factual_authority
        ),
        "human_approval": (
            artifact.human_approval
        ),
        "publication_authority": (
            artifact.publication_authority
        ),
    }

    require(
        artifact.reviewed_social_digest
        == digest(
            payload
        ),
        "reviewed social artifact digest invalid",
    )

    require(
        artifact.authority_state
        == "TEXT_REVIEWED_ONLY",
        "reviewed social artifact authority invalid",
    )

    require(
        artifact.factual_authority
        == "NONE",
        "reviewed social factual authority forbidden",
    )

    require(
        artifact.human_approval
        == "NONE",
        "reviewed social human approval forbidden",
    )

    require(
        artifact.publication_authority
        == "NONE",
        "reviewed social publication authority forbidden",
    )

    return artifact
