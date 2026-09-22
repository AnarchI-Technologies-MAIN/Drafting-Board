"""Atomic verifier execution for admitted Blog review cases.

The verifier is probabilistic and proposal-only.

Deterministic code remains responsible for:
- exact claim identity,
- eligible evidence membership,
- packet identity,
- excerpt identity,
- verdict vocabulary,
- calibration vocabulary,
- temporal vocabulary,
- article-level structural completeness,
- reviewed-artifact identity.

This module creates neither human approval nor publication authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from editorial_claims import CLAIM_EXTRACTOR_VERSION
from editorial_evidence import EVIDENCE_BINDER_VERSION
from editorial_review_artifact import (
    REVIEW_ARTIFACT_VERSION,
    ReviewProvenance,
    ReviewedArticleArtifact,
    build_reviewed_article_artifact,
    validate_artifact,
)
from editorial_verifier import (
    ArticleVerification,
    ClaimVerification,
    build_article_verification,
    CalibrationVerdict,
    FACTUAL_TYPES,
    TemporalSensitivity,
    VerificationVerdict,
)
from editorial_verifier_adapter import (
    VERIFIER_ADAPTER_VERSION,
    VerifierAdapterError,
    VerifierCase,
    build_verifier_prompt,
    parse_verifier_response,
)

from .atomic_review import (
    BlogAtomicReviewCase,
    validate_atomic_review_case,
)


REVIEW_EXECUTION_VERSION = "anarchi.blog-review-execution.v3"

VERIFIER_CONTRACT_ID = (
    "editorial_verifier.py@"
    "sha256:1c90f636b8283b7e5f5fd6a1ba332151"
    "6bd5d717f0a9d86143bbc09cf41caa50"
)


class AtomicReviewExecutionError(ValueError):
    pass


VerifierExecutor = Callable[
    [VerifierCase, list[dict[str, str]]],
    str,
]


@dataclass(frozen=True)
class AtomicReviewExecution:
    schema_version: str
    case: BlogAtomicReviewCase
    claim_verifications: tuple[ClaimVerification, ...]
    article_verification: ArticleVerification
    reviewed_artifact: ReviewedArticleArtifact
    verifier_model: str
    verifier_run_id: str

    @property
    def text_review_passed(self) -> bool:
        return self.reviewed_artifact.text_review_passed

    @property
    def human_adjudication_permitted(self) -> bool:
        return False

    @property
    def publication_permitted(self) -> bool:
        return False


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise AtomicReviewExecutionError(message)


def _execute_one(
    *,
    verifier_case: VerifierCase,
    verifier: VerifierExecutor,
) -> ClaimVerification:
    eligible = (
        verifier_case
        .evidence_set
        .eligible_candidates
    )

    is_material_factual = (
        verifier_case.claim.material
        and verifier_case.claim.claim_type
        in FACTUAL_TYPES
    )

    if (
        is_material_factual
        and not eligible
    ):
        return ClaimVerification(
            claim_id=(
                verifier_case.claim.claim_id
            ),
            claim_text=(
                verifier_case.claim.text
            ),
            claim_type=(
                verifier_case.claim.claim_type
            ),
            material=(
                verifier_case.claim.material
            ),
            verdict=(
                VerificationVerdict
                .INSUFFICIENT_EVIDENCE
            ),
            calibration=(
                CalibrationVerdict.UNASSESSED
            ),
            temporal_sensitivity=(
                TemporalSensitivity.NONE
            ),
            evidence=(),
            rationale=(
                "No eligible evidence was bound "
                "to this material factual claim."
            ),
        )

    prompt = build_verifier_prompt(
        verifier_case
    )

    try:
        raw = verifier(
            verifier_case,
            prompt,
        )
    except Exception as exc:
        raise AtomicReviewExecutionError(
            "verifier execution failed for "
            + verifier_case.claim.claim_id
            + ": "
            + type(exc).__name__
            + ": "
            + str(exc)
        ) from exc

    _require(
        isinstance(raw, str),
        "verifier response must be a string",
    )

    try:
        verification = parse_verifier_response(
            verifier_case,
            raw,
        )
    except VerifierAdapterError as exc:
        raise AtomicReviewExecutionError(
            "verifier response rejected for "
            + verifier_case.claim.claim_id
            + ": "
            + str(exc)
        ) from exc

    _require(
        verification.claim_id
        == verifier_case.claim.claim_id,
        "verification claim identity changed after parsing",
    )

    _require(
        verification.claim_text
        == verifier_case.claim.text,
        "verification claim text changed after parsing",
    )

    _require(
        verification.claim_type
        == verifier_case.claim.claim_type,
        "verification claim type changed after parsing",
    )

    _require(
        verification.material
        == verifier_case.claim.material,
        "verification materiality changed after parsing",
    )

    return verification


def execute_atomic_review(
    *,
    case: BlogAtomicReviewCase,
    verifier: VerifierExecutor,
    verifier_model: str,
    verifier_run_id: str,
) -> AtomicReviewExecution:
    case = validate_atomic_review_case(
        case
    )

    _require(
        isinstance(verifier_model, str)
        and bool(verifier_model.strip()),
        "verifier model identity is required",
    )

    _require(
        isinstance(verifier_run_id, str)
        and bool(verifier_run_id.strip()),
        "verifier run identity is required",
    )

    verifications = tuple(
        _execute_one(
            verifier_case=verifier_case,
            verifier=verifier,
        )
        for verifier_case in case.verifier_cases
    )

    _require(
        len(verifications)
        == len(case.verifier_cases),
        "verification coverage incomplete",
    )

    verification_by_id = {
        item.claim_id: item
        for item in verifications
    }

    _require(
        len(verification_by_id)
        == len(verifications),
        "duplicate verification claim IDs",
    )

    for claim in case.claim_ledger.claims:
        verification = verification_by_id.get(
            claim.claim_id
        )

        _require(
            verification is not None,
            "claim verification missing",
        )

        _require(
            verification.claim_text
            == claim.text,
            "claim verification text mismatch",
        )

        _require(
            verification.claim_type
            == claim.claim_type,
            "claim verification type mismatch",
        )

        _require(
            verification.material
            == claim.material,
            "claim verification materiality mismatch",
        )

    article_verification = (
        build_article_verification(
            case.article_digest,
            case.material_claim_ids,
            verifications,
        )
    )

    provenance = ReviewProvenance(
        extractor_version=CLAIM_EXTRACTOR_VERSION,
        evidence_binder_version=EVIDENCE_BINDER_VERSION,
        verifier_contract_version=VERIFIER_CONTRACT_ID,
        verifier_adapter_version=VERIFIER_ADAPTER_VERSION,
        verifier_model=verifier_model.strip(),
        verifier_run_id=verifier_run_id.strip(),
    )

    artifact = build_reviewed_article_artifact(
        article_text=case.article_text,
        claim_ledger=case.claim_ledger,
        evidence_sets=case.evidence_sets,
        article_verification=article_verification,
        repair_history=(),
        provenance=provenance,
    )

    artifact_errors = validate_artifact(
        artifact
    )

    _require(
        not artifact_errors,
        "reviewed artifact validation failed: "
        + "; ".join(artifact_errors),
    )

    _require(
        artifact.schema_version
        == REVIEW_ARTIFACT_VERSION,
        "reviewed artifact schema mismatch",
    )

    _require(
        artifact.article_digest
        == case.article_digest,
        "reviewed artifact article identity mismatch",
    )

    _require(
        artifact.human_adjudication_permitted
        is False,
        "review artifact cannot grant human adjudication",
    )

    _require(
        artifact.publication_permitted
        is False,
        "review artifact cannot grant publication",
    )

    return AtomicReviewExecution(
        schema_version=REVIEW_EXECUTION_VERSION,
        case=case,
        claim_verifications=verifications,
        article_verification=article_verification,
        reviewed_artifact=artifact,
        verifier_model=verifier_model.strip(),
        verifier_run_id=verifier_run_id.strip(),
    )
