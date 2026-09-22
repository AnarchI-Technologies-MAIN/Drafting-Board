import unittest

from editorial_claims import ExtractedClaimType
from editorial_verifier import (
    CalibrationVerdict,
    ClaimVerification,
    TemporalSensitivity,
    VerificationVerdict,
    VerifiedEvidence,
    build_article_verification,
)


def evidence(packet_id: int = 1):
    return (
        VerifiedEvidence(
            packet_id=packet_id,
            source_url="https://example.invalid/source",
            excerpt_digest=f"digest-{packet_id}",
        ),
    )


def verified_claim(
    claim_id: str,
    *,
    claim_type=ExtractedClaimType.FACT,
    verdict=VerificationVerdict.SUPPORTED,
    calibration=CalibrationVerdict.PRECISE,
    material=True,
    attached_evidence=None,
):
    if attached_evidence is None:
        attached_evidence = evidence()

    return ClaimVerification(
        claim_id=claim_id,
        claim_text="Atomic specimen.",
        claim_type=claim_type,
        material=material,
        verdict=verdict,
        calibration=calibration,
        evidence=attached_evidence,
    )


class EditorialVerifierContractTests(unittest.TestCase):
    def test_supported_precise_fact_with_evidence_passes(self):
        item = verified_claim("claim-1")
        self.assertTrue(item.acceptable)

    def test_supported_fact_without_evidence_fails(self):
        item = verified_claim(
            "claim-2",
            attached_evidence=(),
        )
        self.assertFalse(item.acceptable)

    def test_contradicted_claim_fails(self):
        item = verified_claim(
            "claim-3",
            verdict=VerificationVerdict.CONTRADICTED,
        )
        self.assertFalse(item.acceptable)

    def test_insufficient_evidence_fails(self):
        item = verified_claim(
            "claim-4",
            verdict=VerificationVerdict.INSUFFICIENT_EVIDENCE,
            attached_evidence=(),
        )
        self.assertFalse(item.acceptable)

    def test_ambiguous_claim_fails(self):
        item = verified_claim(
            "claim-5",
            verdict=VerificationVerdict.AMBIGUOUS,
        )
        self.assertFalse(item.acceptable)

    def test_stale_claim_fails(self):
        item = ClaimVerification(
            claim_id="claim-6",
            claim_text="A current product behavior.",
            claim_type=ExtractedClaimType.TEMPORAL,
            material=True,
            verdict=VerificationVerdict.STALE,
            calibration=CalibrationVerdict.PRECISE,
            temporal_sensitivity=TemporalSensitivity.HIGH,
            evidence=evidence(6),
        )
        self.assertFalse(item.acceptable)

    def test_overstatement_fails_even_when_supported(self):
        item = verified_claim(
            "claim-7",
            verdict=VerificationVerdict.SUPPORTED,
            calibration=CalibrationVerdict.OVERSTATED,
        )
        self.assertFalse(item.acceptable)

    def test_misleading_wording_fails_even_when_supported(self):
        item = verified_claim(
            "claim-8",
            verdict=VerificationVerdict.SUPPORTED,
            calibration=CalibrationVerdict.MISLEADING,
        )
        self.assertFalse(item.acceptable)

    def test_one_fracture_fails_entire_article(self):
        good = verified_claim("claim-9")
        bad = verified_claim(
            "claim-10",
            verdict=VerificationVerdict.CONTRADICTED,
        )

        result = build_article_verification(
            "article-digest",
            ["claim-9", "claim-10"],
            [good, bad],
        )

        self.assertFalse(result.passed)
        self.assertEqual(
            [item.claim_id for item in result.fractures],
            ["claim-10"],
        )

    def test_missing_material_claim_fails_closed(self):
        result = build_article_verification(
            "article-digest",
            ["claim-11", "claim-12"],
            [verified_claim("claim-11")],
        )

        self.assertFalse(result.structurally_complete)
        self.assertFalse(result.passed)
        self.assertEqual(
            result.missing_material_claim_ids,
            ("claim-12",),
        )

    def test_duplicate_claim_verdict_fails_closed(self):
        result = build_article_verification(
            "article-digest",
            ["claim-13"],
            [
                verified_claim("claim-13"),
                verified_claim("claim-13"),
            ],
        )

        self.assertFalse(result.structurally_complete)
        self.assertFalse(result.passed)
        self.assertEqual(
            result.duplicate_claim_ids,
            ("claim-13",),
        )

    def test_unexpected_material_claim_fails_closed(self):
        result = build_article_verification(
            "article-digest",
            ["claim-14"],
            [
                verified_claim("claim-14"),
                verified_claim("claim-unknown"),
            ],
        )

        self.assertFalse(result.structurally_complete)
        self.assertFalse(result.passed)

    def test_all_material_claims_must_pass(self):
        claims = [
            verified_claim("claim-15"),
            verified_claim(
                "claim-16",
                claim_type=ExtractedClaimType.CAPABILITY,
            ),
            verified_claim(
                "claim-17",
                claim_type=ExtractedClaimType.CONFIGURATION,
            ),
        ]

        result = build_article_verification(
            "article-digest",
            ["claim-15", "claim-16", "claim-17"],
            claims,
        )

        self.assertTrue(result.structurally_complete)
        self.assertTrue(result.passed)
        self.assertTrue(result.image_handoff_permitted)

    def test_nonfactual_rhetoric_can_pass_without_evidence(self):
        item = ClaimVerification(
            claim_id="claim-18",
            claim_text="A quieter failure is still a failure.",
            claim_type=ExtractedClaimType.RHETORICAL,
            material=True,
            verdict=VerificationVerdict.NON_FACTUAL,
            calibration=CalibrationVerdict.PRECISE,
            evidence=(),
        )

        self.assertTrue(item.acceptable)

    def test_verifier_cannot_grant_human_adjudication(self):
        result = build_article_verification(
            "article-digest",
            ["claim-19"],
            [verified_claim("claim-19")],
        )

        self.assertFalse(
            result.human_adjudication_permitted
        )

    def test_verifier_cannot_grant_publication(self):
        result = build_article_verification(
            "article-digest",
            ["claim-20"],
            [verified_claim("claim-20")],
        )

        self.assertFalse(result.publication_permitted)


if __name__ == "__main__":
    unittest.main()
