import unittest
from dataclasses import replace

from editorial_claims import (
    extract_claims,
)
from editorial_evidence import (
    EvidenceSource,
    bind_evidence_candidates,
)
from editorial_verifier import (
    CalibrationVerdict,
    ClaimVerification,
    VerificationVerdict,
    VerifiedEvidence,
    build_article_verification,
)
from editorial_review_artifact import (
    REVIEW_ARTIFACT_VERSION,
    RepairRecord,
    ReviewProvenance,
    artifact_payload,
    build_reviewed_article_artifact,
    digest_payload,
    validate_artifact,
)


ARTICLE = (
    "Docker contexts can select different daemon endpoints."
)


def specimen():
    ledger = extract_claims(ARTICLE)
    claim = ledger.claims[0]

    binding = bind_evidence_candidates(
        claim,
        [
            EvidenceSource(
                packet_id=11001,
                title="Docker context documentation",
                url="https://example.invalid/docker",
                excerpt=(
                    "Docker contexts allow a client to select "
                    "different daemon endpoints."
                ),
                provider="documentation",
                relevance_passed=True,
            )
        ],
    )

    candidate = binding.eligible_candidates[0]

    verification = ClaimVerification(
        claim_id=claim.claim_id,
        claim_text=claim.text,
        claim_type=claim.claim_type,
        material=claim.material,
        verdict=VerificationVerdict.SUPPORTED,
        calibration=CalibrationVerdict.PRECISE,
        evidence=(
            VerifiedEvidence(
                packet_id=candidate.packet_id,
                source_url=candidate.source_url,
                excerpt_digest=candidate.excerpt_digest,
            ),
        ),
        rationale=(
            "The bound evidence directly supports the claim."
        ),
    )

    article_verification = build_article_verification(
        ledger.article_digest,
        [claim.claim_id],
        [verification],
    )

    provenance = ReviewProvenance(
        extractor_version=ledger.extractor_version,
        evidence_binder_version="anarchi.editorial-evidence.v1",
        verifier_contract_version="anarchi.editorial-verifier.v1",
        verifier_adapter_version=(
            "anarchi.editorial-verifier-adapter.v1"
        ),
        verifier_model="granite4:tiny-h",
        verifier_run_id="specimen-run-001",
    )

    artifact = build_reviewed_article_artifact(
        article_text=ARTICLE,
        claim_ledger=ledger,
        evidence_sets=[binding],
        article_verification=article_verification,
        repair_history=[],
        provenance=provenance,
    )

    return artifact


class ReviewedArticleArtifactTests(unittest.TestCase):
    def test_version_is_stable(self):
        self.assertEqual(
            REVIEW_ARTIFACT_VERSION,
            "anarchi.reviewed-article.v1",
        )

    def test_clean_artifact_validates(self):
        artifact = specimen()
        self.assertEqual(
            validate_artifact(artifact),
            (),
        )

    def test_digest_is_stable(self):
        first = specimen()
        second = specimen()

        self.assertEqual(
            first.artifact_digest,
            second.artifact_digest,
        )

    def test_exact_payload_digest_matches_artifact(self):
        artifact = specimen()

        self.assertEqual(
            artifact.artifact_digest,
            digest_payload(
                artifact_payload(artifact)
            ),
        )

    def test_clean_review_permits_image_handoff(self):
        artifact = specimen()

        self.assertTrue(
            artifact.text_review_passed
        )
        self.assertTrue(
            artifact.image_handoff_permitted
        )

    def test_artifact_never_grants_human_adjudication(self):
        artifact = specimen()

        self.assertFalse(
            artifact.human_adjudication_permitted
        )

    def test_artifact_never_grants_publication(self):
        artifact = specimen()

        self.assertFalse(
            artifact.publication_permitted
        )

    def test_article_text_change_changes_digest(self):
        artifact = specimen()

        mutated = replace(
            artifact,
            article_text=(
                artifact.article_text
                + " Additional sentence."
            ),
        )

        self.assertNotEqual(
            artifact.artifact_digest,
            mutated.artifact_digest,
        )

    def test_verdict_change_changes_digest(self):
        artifact = specimen()

        original = artifact.article_verification.claims[0]

        changed = replace(
            original,
            verdict=VerificationVerdict.CONTRADICTED,
        )

        changed_article = build_article_verification(
            artifact.article_digest,
            artifact.article_verification.expected_material_claim_ids,
            [changed],
        )

        mutated = replace(
            artifact,
            article_verification=changed_article,
        )

        self.assertNotEqual(
            artifact.artifact_digest,
            mutated.artifact_digest,
        )

    def test_calibration_change_changes_digest(self):
        artifact = specimen()

        original = artifact.article_verification.claims[0]

        changed = replace(
            original,
            calibration=CalibrationVerdict.OVERSTATED,
        )

        changed_article = build_article_verification(
            artifact.article_digest,
            artifact.article_verification.expected_material_claim_ids,
            [changed],
        )

        mutated = replace(
            artifact,
            article_verification=changed_article,
        )

        self.assertNotEqual(
            artifact.artifact_digest,
            mutated.artifact_digest,
        )

    def test_evidence_digest_change_changes_artifact_digest(self):
        artifact = specimen()

        evidence_set = artifact.evidence_sets[0]
        candidate = evidence_set.candidates[0]

        changed_candidate = replace(
            candidate,
            excerpt_digest="changed-digest",
        )

        changed_set = replace(
            evidence_set,
            candidates=(changed_candidate,),
        )

        mutated = replace(
            artifact,
            evidence_sets=(changed_set,),
        )

        self.assertNotEqual(
            artifact.artifact_digest,
            mutated.artifact_digest,
        )

    def test_model_identity_change_changes_digest(self):
        artifact = specimen()

        mutated = replace(
            artifact,
            provenance=replace(
                artifact.provenance,
                verifier_model="different-model",
            ),
        )

        self.assertNotEqual(
            artifact.artifact_digest,
            mutated.artifact_digest,
        )

    def test_repair_history_changes_digest(self):
        artifact = specimen()

        repair = RepairRecord(
            repair_id="repair-001",
            affected_claim_ids=artifact.material_claim_ids,
            reason="Bounded wording correction.",
            before_digest="before",
            after_digest="after",
        )

        mutated = replace(
            artifact,
            repair_history=(repair,),
        )

        self.assertNotEqual(
            artifact.artifact_digest,
            mutated.artifact_digest,
        )

    def test_unbound_verified_evidence_fails_validation(self):
        artifact = specimen()

        verification = artifact.article_verification.claims[0]

        changed = replace(
            verification,
            evidence=(
                VerifiedEvidence(
                    packet_id=999999,
                    source_url="https://example.invalid/invented",
                    excerpt_digest="invented",
                ),
            ),
        )

        changed_article = build_article_verification(
            artifact.article_digest,
            artifact.material_claim_ids,
            [changed],
        )

        invalid = replace(
            artifact,
            article_verification=changed_article,
        )

        errors = validate_artifact(invalid)

        self.assertTrue(
            any(
                "unbound evidence" in error
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
