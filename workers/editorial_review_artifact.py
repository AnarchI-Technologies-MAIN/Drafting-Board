"""Immutable reviewed-article artifact contract.

A ReviewedArticleArtifact is the sealed case file produced after
atomic editorial verification.

It commits to:
- exact article content,
- extracted material claims,
- evidence identities,
- atomic verdicts,
- review provenance,
- repair history,
- downstream gate state.

Changing any committed truth-bearing field changes artifact identity.

This artifact may authorize Illustration Lab handoff when text review
passes. It grants no human adjudication authority and no publication
authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable

from editorial_claims import (
    ClaimLedger,
    ExtractedClaim,
)
from editorial_evidence import (
    ClaimEvidenceSet,
)
from editorial_verifier import (
    ArticleVerification,
    ClaimVerification,
)


REVIEW_ARTIFACT_VERSION = "anarchi.reviewed-article.v1"


@dataclass(frozen=True)
class RepairRecord:
    repair_id: str
    affected_claim_ids: tuple[str, ...]
    reason: str
    before_digest: str
    after_digest: str


@dataclass(frozen=True)
class ReviewProvenance:
    extractor_version: str
    evidence_binder_version: str
    verifier_contract_version: str
    verifier_adapter_version: str
    verifier_model: str
    verifier_run_id: str


@dataclass(frozen=True)
class ReviewedArticleArtifact:
    schema_version: str
    article_text: str
    article_digest: str
    claim_ledger: ClaimLedger
    evidence_sets: tuple[ClaimEvidenceSet, ...]
    article_verification: ArticleVerification
    repair_history: tuple[RepairRecord, ...]
    provenance: ReviewProvenance

    @property
    def text_review_passed(self) -> bool:
        return self.article_verification.passed

    @property
    def image_handoff_permitted(self) -> bool:
        return self.article_verification.passed

    @property
    def human_adjudication_permitted(self) -> bool:
        return False

    @property
    def publication_permitted(self) -> bool:
        return False

    @property
    def material_claim_ids(self) -> tuple[str, ...]:
        return tuple(
            claim.claim_id
            for claim in self.claim_ledger.claims
            if claim.material
        )

    @property
    def artifact_digest(self) -> str:
        return digest_payload(
            artifact_payload(self)
        )


def _claim_payload(
    claim: ExtractedClaim,
) -> dict:
    return {
        "claim_id": claim.claim_id,
        "text": claim.text,
        "claim_type": claim.claim_type.value,
        "material": claim.material,
        "source_span_start": claim.source_span_start,
        "source_span_end": claim.source_span_end,
    }


def _evidence_payload(
    evidence_set: ClaimEvidenceSet,
) -> dict:
    return {
        "claim_id": evidence_set.claim_id,
        "candidates": [
            {
                "packet_id": candidate.packet_id,
                "source_url": candidate.source_url,
                "source_title": candidate.source_title,
                "provider": candidate.provider,
                "excerpt": candidate.excerpt,
                "excerpt_digest": candidate.excerpt_digest,
                "shared_terms": list(candidate.shared_terms),
                "retrieval_score": candidate.retrieval_score,
                "eligible": candidate.eligible,
            }
            for candidate in evidence_set.candidates
        ],
    }


def _verification_payload(
    verification: ClaimVerification,
) -> dict:
    return {
        "claim_id": verification.claim_id,
        "claim_text": verification.claim_text,
        "claim_type": verification.claim_type.value,
        "material": verification.material,
        "verdict": verification.verdict.value,
        "calibration": verification.calibration.value,
        "temporal_sensitivity": (
            verification.temporal_sensitivity.value
        ),
        "evidence": [
            {
                "packet_id": item.packet_id,
                "source_url": item.source_url,
                "excerpt_digest": item.excerpt_digest,
            }
            for item in verification.evidence
        ],
        "rationale": verification.rationale,
        "acceptable": verification.acceptable,
    }


def artifact_payload(
    artifact: ReviewedArticleArtifact,
) -> dict:
    return {
        "schema_version": artifact.schema_version,
        "article_text": artifact.article_text,
        "article_digest": artifact.article_digest,
        "claim_ledger": {
            "article_digest": artifact.claim_ledger.article_digest,
            "extractor_version": artifact.claim_ledger.extractor_version,
            "claims": [
                _claim_payload(claim)
                for claim in artifact.claim_ledger.claims
            ],
        },
        "evidence_sets": [
            _evidence_payload(item)
            for item in artifact.evidence_sets
        ],
        "verification": {
            "article_digest": (
                artifact.article_verification.article_digest
            ),
            "expected_material_claim_ids": list(
                artifact.article_verification.expected_material_claim_ids
            ),
            "claims": [
                _verification_payload(item)
                for item in artifact.article_verification.claims
            ],
            "structurally_complete": (
                artifact.article_verification.structurally_complete
            ),
            "passed": artifact.article_verification.passed,
            "fracture_claim_ids": [
                item.claim_id
                for item in artifact.article_verification.fractures
            ],
        },
        "repair_history": [
            {
                "repair_id": item.repair_id,
                "affected_claim_ids": list(
                    item.affected_claim_ids
                ),
                "reason": item.reason,
                "before_digest": item.before_digest,
                "after_digest": item.after_digest,
            }
            for item in artifact.repair_history
        ],
        "provenance": {
            "extractor_version": (
                artifact.provenance.extractor_version
            ),
            "evidence_binder_version": (
                artifact.provenance.evidence_binder_version
            ),
            "verifier_contract_version": (
                artifact.provenance.verifier_contract_version
            ),
            "verifier_adapter_version": (
                artifact.provenance.verifier_adapter_version
            ),
            "verifier_model": (
                artifact.provenance.verifier_model
            ),
            "verifier_run_id": (
                artifact.provenance.verifier_run_id
            ),
        },
        "gates": {
            "text_review_passed": artifact.text_review_passed,
            "image_handoff_permitted": (
                artifact.image_handoff_permitted
            ),
            "human_adjudication_permitted": False,
            "publication_permitted": False,
        },
    }


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
        canonical_json(payload).encode("utf-8")
    ).hexdigest()


def validate_artifact(
    artifact: ReviewedArticleArtifact,
) -> tuple[str, ...]:
    errors: list[str] = []

    if artifact.schema_version != REVIEW_ARTIFACT_VERSION:
        errors.append("schema version mismatch")

    if artifact.article_digest != artifact.claim_ledger.article_digest:
        errors.append(
            "article digest does not match claim ledger"
        )

    if (
        artifact.article_digest
        != artifact.article_verification.article_digest
    ):
        errors.append(
            "article digest does not match verification"
        )

    material_ids = artifact.material_claim_ids

    if (
        material_ids
        != artifact.article_verification.expected_material_claim_ids
    ):
        errors.append(
            "material claim identity mismatch"
        )

    ledger_ids = {
        claim.claim_id
        for claim in artifact.claim_ledger.claims
    }

    evidence_ids = {
        item.claim_id
        for item in artifact.evidence_sets
    }

    verification_ids = {
        item.claim_id
        for item in artifact.article_verification.claims
    }

    unknown_evidence_ids = sorted(
        evidence_ids.difference(ledger_ids)
    )

    if unknown_evidence_ids:
        errors.append(
            "evidence references unknown claim IDs"
        )

    unknown_verification_ids = sorted(
        verification_ids.difference(ledger_ids)
    )

    if unknown_verification_ids:
        errors.append(
            "verification references unknown claim IDs"
        )

    for verification in artifact.article_verification.claims:
        matching_sets = [
            item
            for item in artifact.evidence_sets
            if item.claim_id == verification.claim_id
        ]

        eligible = {
            (
                candidate.packet_id,
                candidate.source_url,
                candidate.excerpt_digest,
            )
            for evidence_set in matching_sets
            for candidate in evidence_set.eligible_candidates
        }

        for evidence in verification.evidence:
            identity = (
                evidence.packet_id,
                evidence.source_url,
                evidence.excerpt_digest,
            )

            if identity not in eligible:
                errors.append(
                    "verification relies on unbound evidence: "
                    + verification.claim_id
                )

    return tuple(errors)


def build_reviewed_article_artifact(
    *,
    article_text: str,
    claim_ledger: ClaimLedger,
    evidence_sets: Iterable[ClaimEvidenceSet],
    article_verification: ArticleVerification,
    repair_history: Iterable[RepairRecord],
    provenance: ReviewProvenance,
) -> ReviewedArticleArtifact:
    artifact = ReviewedArticleArtifact(
        schema_version=REVIEW_ARTIFACT_VERSION,
        article_text=article_text,
        article_digest=claim_ledger.article_digest,
        claim_ledger=claim_ledger,
        evidence_sets=tuple(evidence_sets),
        article_verification=article_verification,
        repair_history=tuple(repair_history),
        provenance=provenance,
    )

    errors = validate_artifact(artifact)

    if errors:
        raise ValueError(
            "; ".join(errors)
        )

    return artifact
