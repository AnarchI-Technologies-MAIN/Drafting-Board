"""Atomic verification verdict contracts for AnarchI Editorial Foundry.

This module defines the shape and deterministic acceptance semantics of
claim-level factual verification.

It does not itself determine whether evidence supports a claim.
A later verifier implementation must produce records satisfying this contract.

No human adjudication or publication authority exists here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from editorial_claims import ExtractedClaimType


VERIFIER_CONTRACT_VERSION = "anarchi.editorial-verifier.v2"


class VerificationVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    AMBIGUOUS = "AMBIGUOUS"
    STALE = "STALE"
    NON_FACTUAL = "NON_FACTUAL"


class CalibrationVerdict(str, Enum):
    PRECISE = "PRECISE"
    OVERSTATED = "OVERSTATED"
    UNDERSTATED = "UNDERSTATED"
    MISLEADING = "MISLEADING"
    UNASSESSED = "UNASSESSED"


class TemporalSensitivity(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


FACTUAL_TYPES = frozenset(
    {
        ExtractedClaimType.FACT,
        ExtractedClaimType.CAUSAL,
        ExtractedClaimType.COMMAND,
        ExtractedClaimType.CONFIGURATION,
        ExtractedClaimType.CAPABILITY,
        ExtractedClaimType.BENCHMARK,
        ExtractedClaimType.TEMPORAL,
    }
)


@dataclass(frozen=True)
class VerifiedEvidence:
    packet_id: int
    source_url: str
    excerpt_digest: str


@dataclass(frozen=True)
class ClaimVerification:
    claim_id: str
    claim_text: str
    claim_type: ExtractedClaimType
    material: bool
    verdict: VerificationVerdict
    calibration: CalibrationVerdict
    temporal_sensitivity: TemporalSensitivity = TemporalSensitivity.NONE
    evidence: tuple[VerifiedEvidence, ...] = field(default_factory=tuple)
    rationale: str = ""

    @property
    def requires_factual_support(self) -> bool:
        return (
            self.material
            and self.claim_type in FACTUAL_TYPES
        )

    @property
    def has_verified_evidence(self) -> bool:
        return bool(self.evidence)

    @property
    def acceptable(self) -> bool:
        if not self.material:
            return True

        if self.claim_type in {
            ExtractedClaimType.OPINION,
            ExtractedClaimType.RHETORICAL,
        }:
            return (
                self.verdict == VerificationVerdict.NON_FACTUAL
            )

        if self.claim_type == ExtractedClaimType.INFERENCE:
            return (
                self.verdict
                in {
                    VerificationVerdict.SUPPORTED,
                    VerificationVerdict.NON_FACTUAL,
                }
                and self.calibration
                == CalibrationVerdict.PRECISE
            )

        if self.claim_type == ExtractedClaimType.RECOMMENDATION:
            return (
                self.verdict
                in {
                    VerificationVerdict.SUPPORTED,
                    VerificationVerdict.NON_FACTUAL,
                }
                and self.calibration
                == CalibrationVerdict.PRECISE
            )

        if self.requires_factual_support:
            return (
                self.verdict
                == VerificationVerdict.SUPPORTED
                and self.calibration
                == CalibrationVerdict.PRECISE
                and self.has_verified_evidence
            )

        return False


@dataclass(frozen=True)
class ArticleVerification:
    article_digest: str
    expected_material_claim_ids: tuple[str, ...]
    claims: tuple[ClaimVerification, ...]

    @property
    def observed_material_claim_ids(self) -> tuple[str, ...]:
        return tuple(
            item.claim_id
            for item in self.claims
            if item.material
        )

    @property
    def missing_material_claim_ids(self) -> tuple[str, ...]:
        observed = set(self.observed_material_claim_ids)

        return tuple(
            claim_id
            for claim_id in self.expected_material_claim_ids
            if claim_id not in observed
        )

    @property
    def duplicate_claim_ids(self) -> tuple[str, ...]:
        seen: set[str] = set()
        duplicates: list[str] = []

        for item in self.claims:
            if item.claim_id in seen:
                duplicates.append(item.claim_id)
            seen.add(item.claim_id)

        return tuple(sorted(set(duplicates)))

    @property
    def unexpected_material_claim_ids(self) -> tuple[str, ...]:
        expected = set(self.expected_material_claim_ids)

        return tuple(
            sorted(
                {
                    item.claim_id
                    for item in self.claims
                    if item.material
                    and item.claim_id not in expected
                }
            )
        )

    @property
    def fractures(self) -> tuple[ClaimVerification, ...]:
        return tuple(
            item
            for item in self.claims
            if item.material and not item.acceptable
        )

    @property
    def structurally_complete(self) -> bool:
        return (
            bool(self.expected_material_claim_ids)
            and not self.missing_material_claim_ids
            and not self.duplicate_claim_ids
            and not self.unexpected_material_claim_ids
        )

    @property
    def passed(self) -> bool:
        return (
            self.structurally_complete
            and not self.fractures
        )

    @property
    def image_handoff_permitted(self) -> bool:
        return self.passed

    @property
    def human_adjudication_permitted(self) -> bool:
        return False

    @property
    def publication_permitted(self) -> bool:
        return False


def build_article_verification(
    article_digest: str,
    expected_material_claim_ids: Iterable[str],
    claims: Iterable[ClaimVerification],
) -> ArticleVerification:
    return ArticleVerification(
        article_digest=article_digest,
        expected_material_claim_ids=tuple(
            expected_material_claim_ids
        ),
        claims=tuple(claims),
    )
