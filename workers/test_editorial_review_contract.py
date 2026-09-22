import unittest

from editorial_review_contract import (
    ArticleReviewGate,
    AtomicClaimReview,
    CalibrationVerdict,
    ClaimType,
    ClaimVerdict,
    EvidenceBinding,
    TemporalSensitivity,
    review_gate,
)


def evidence(packet_id: int = 1) -> tuple[EvidenceBinding, ...]:
    return (
        EvidenceBinding(
            packet_id=packet_id,
            source_url="https://example.invalid/source",
            source_digest="sha256:test",
        ),
    )


class AtomicReviewContractTests(unittest.TestCase):
    def test_supported_material_fact_with_evidence_passes(self):
        claim = AtomicClaimReview(
            claim_id="claim-001",
            text="A supported material fact.",
            claim_type=ClaimType.FACT,
            material=True,
            verdict=ClaimVerdict.SUPPORTED,
            calibration=CalibrationVerdict.PRECISE,
            evidence=evidence(),
        )
        self.assertTrue(claim.acceptable)

    def test_supported_material_fact_without_evidence_fails(self):
        claim = AtomicClaimReview(
            claim_id="claim-002",
            text="A fact cannot support itself.",
            claim_type=ClaimType.FACT,
            material=True,
            verdict=ClaimVerdict.SUPPORTED,
            calibration=CalibrationVerdict.PRECISE,
        )
        self.assertFalse(claim.acceptable)

    def test_one_contradicted_claim_fractures_whole_article(self):
        good = AtomicClaimReview(
            claim_id="claim-003",
            text="Supported.",
            claim_type=ClaimType.FACT,
            material=True,
            verdict=ClaimVerdict.SUPPORTED,
            calibration=CalibrationVerdict.PRECISE,
            evidence=evidence(3),
        )
        bad = AtomicClaimReview(
            claim_id="claim-004",
            text="Contradicted.",
            claim_type=ClaimType.CAUSAL,
            material=True,
            verdict=ClaimVerdict.CONTRADICTED,
            calibration=CalibrationVerdict.PRECISE,
            evidence=evidence(4),
        )
        gate = review_gate("article-1", "digest-1", [good, bad])
        self.assertFalse(gate.passed)
        self.assertEqual([claim.claim_id for claim in gate.fractures], ["claim-004"])

    def test_overstatement_fractures_supported_claim(self):
        claim = AtomicClaimReview(
            claim_id="claim-005",
            text="Evidence says may; prose says always.",
            claim_type=ClaimType.CAPABILITY,
            material=True,
            verdict=ClaimVerdict.SUPPORTED,
            calibration=CalibrationVerdict.OVERSTATED,
            evidence=evidence(5),
        )
        self.assertFalse(claim.acceptable)

    def test_stale_claim_fails(self):
        claim = AtomicClaimReview(
            claim_id="claim-006",
            text="Time-sensitive claim.",
            claim_type=ClaimType.TEMPORAL,
            material=True,
            verdict=ClaimVerdict.STALE,
            calibration=CalibrationVerdict.PRECISE,
            temporal_sensitivity=TemporalSensitivity.HIGH,
            evidence=evidence(6),
        )
        self.assertFalse(claim.acceptable)

    def test_rhetorical_voice_does_not_require_source(self):
        claim = AtomicClaimReview(
            claim_id="claim-007",
            text="A little kiln fire in the prose.",
            claim_type=ClaimType.RHETORICAL,
            material=True,
            verdict=ClaimVerdict.NON_FACTUAL,
            calibration=CalibrationVerdict.PRECISE,
        )
        self.assertTrue(claim.acceptable)

    def test_nonmaterial_claim_does_not_block(self):
        claim = AtomicClaimReview(
            claim_id="claim-008",
            text="Decorative prose.",
            claim_type=ClaimType.OPINION,
            material=False,
            verdict=ClaimVerdict.AMBIGUOUS,
            calibration=CalibrationVerdict.MISLEADING,
        )
        self.assertTrue(claim.acceptable)

    def test_clean_article_permits_image_handoff(self):
        claim = AtomicClaimReview(
            claim_id="claim-009",
            text="Supported.",
            claim_type=ClaimType.CONFIGURATION,
            material=True,
            verdict=ClaimVerdict.SUPPORTED,
            calibration=CalibrationVerdict.PRECISE,
            evidence=evidence(9),
        )
        gate = review_gate("article-2", "digest-2", [claim])
        self.assertTrue(gate.passed)
        self.assertTrue(gate.image_handoff_permitted)

    def test_atomic_review_never_grants_human_adjudication(self):
        claim = AtomicClaimReview(
            claim_id="claim-010",
            text="Supported.",
            claim_type=ClaimType.FACT,
            material=True,
            verdict=ClaimVerdict.SUPPORTED,
            calibration=CalibrationVerdict.PRECISE,
            evidence=evidence(10),
        )
        gate = review_gate("article-3", "digest-3", [claim])
        self.assertFalse(gate.human_adjudication_permitted)

    def test_atomic_review_never_grants_publication(self):
        claim = AtomicClaimReview(
            claim_id="claim-011",
            text="Supported.",
            claim_type=ClaimType.FACT,
            material=True,
            verdict=ClaimVerdict.SUPPORTED,
            calibration=CalibrationVerdict.PRECISE,
            evidence=evidence(11),
        )
        gate = review_gate("article-4", "digest-4", [claim])
        self.assertFalse(gate.publication_permitted)

    def test_zero_material_claims_fail_closed(self):
        gate = ArticleReviewGate(
            article_id="article-5",
            article_digest="digest-5",
            claims=(),
        )
        self.assertFalse(gate.passed)
        self.assertFalse(gate.image_handoff_permitted)


if __name__ == "__main__":
    unittest.main()
