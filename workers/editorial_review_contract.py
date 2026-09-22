"""Deterministic contracts for atomic editorial verification.

This module grants no factual, adjudication, publication, or execution
authority. It defines how material claims must be dispositioned before an
editorial artifact may proceed to the creative-image handoff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class ClaimType(str, Enum):
    FACT = "FACT"
    CAUSAL = "CAUSAL"
    COMMAND = "COMMAND"
    CONFIGURATION = "CONFIGURATION"
    CAPABILITY = "CAPABILITY"
    BENCHMARK = "BENCHMARK"
    TEMPORAL = "TEMPORAL"
    RECOMMENDATION = "RECOMMENDATION"
    INFERENCE = "INFERENCE"
    OPINION = "OPINION"
    RHETORICAL = "RHETORICAL"


class ClaimVerdict(str, Enum):
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


class TemporalSensitivity(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


FACTUAL_CLAIM_TYPES = frozenset(
    {
        ClaimType.FACT,
        ClaimType.CAUSAL,
        ClaimType.COMMAND,
        ClaimType.CONFIGURATION,
        ClaimType.CAPABILITY,
        ClaimType.BENCHMARK,
        ClaimType.TEMPORAL,
    }
)


@dataclass(frozen=True)
class EvidenceBinding:
    packet_id: int
    source_url: str
    source_digest: str = ""


@dataclass(frozen=True)
class AtomicClaimReview:
    claim_id: str
    text: str
    claim_type: ClaimType
    material: bool
    verdict: ClaimVerdict
    calibration: CalibrationVerdict
    temporal_sensitivity: TemporalSensitivity = TemporalSensitivity.NONE
    evidence: tuple[EvidenceBinding, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def requires_factual_support(self) -> bool:
        return self.material and self.claim_type in FACTUAL_CLAIM_TYPES

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence)

    @property
    def acceptable(self) -> bool:
        if not self.material:
            return True

        if self.claim_type in {ClaimType.OPINION, ClaimType.RHETORICAL}:
            return self.verdict == ClaimVerdict.NON_FACTUAL

        if self.claim_type == ClaimType.INFERENCE:
            return (
                self.verdict in {
                    ClaimVerdict.SUPPORTED,
                    ClaimVerdict.NON_FACTUAL,
                }
                and self.calibration == CalibrationVerdict.PRECISE
            )

        if self.requires_factual_support:
            return (
                self.verdict == ClaimVerdict.SUPPORTED
                and self.has_evidence
                and self.calibration == CalibrationVerdict.PRECISE
            )

        if self.claim_type == ClaimType.RECOMMENDATION:
            return (
                self.verdict in {
                    ClaimVerdict.SUPPORTED,
                    ClaimVerdict.NON_FACTUAL,
                }
                and self.calibration == CalibrationVerdict.PRECISE
            )

        return False


@dataclass(frozen=True)
class ArticleReviewGate:
    article_id: str
    article_digest: str
    claims: tuple[AtomicClaimReview, ...]

    @property
    def material_claims(self) -> tuple[AtomicClaimReview, ...]:
        return tuple(claim for claim in self.claims if claim.material)

    @property
    def fractures(self) -> tuple[AtomicClaimReview, ...]:
        return tuple(
            claim
            for claim in self.material_claims
            if not claim.acceptable
        )

    @property
    def passed(self) -> bool:
        return bool(self.material_claims) and not self.fractures

    @property
    def image_handoff_permitted(self) -> bool:
        return self.passed

    @property
    def human_adjudication_permitted(self) -> bool:
        # Human adjudication belongs downstream after image materialization
        # and visual validation. Atomic editorial review alone cannot grant it.
        return False

    @property
    def publication_permitted(self) -> bool:
        return False


def review_gate(
    article_id: str,
    article_digest: str,
    claims: Iterable[AtomicClaimReview],
) -> ArticleReviewGate:
    return ArticleReviewGate(
        article_id=article_id,
        article_digest=article_digest,
        claims=tuple(claims),
    )
