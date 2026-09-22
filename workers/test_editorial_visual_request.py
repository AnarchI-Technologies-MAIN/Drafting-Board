import unittest
from dataclasses import replace

from editorial_claims import (
    extract_claims,
)
from editorial_evidence import (
    EvidenceSource,
    bind_evidence_candidates,
)
from editorial_review_artifact import (
    REVIEW_ARTIFACT_VERSION,
    ReviewProvenance,
    build_reviewed_article_artifact,
)
from editorial_verifier import (
    CalibrationVerdict,
    ClaimVerification,
    TemporalSensitivity,
    VerificationVerdict,
    VerifiedEvidence,
    build_article_verification,
)
from editorial_visual_request import (
    EDITORIAL_VISUAL_REQUEST_VERSION,
    VisualPurpose,
    build_editorial_visual_request,
    validate_request,
)


def specimen_artifact():
    article = (
        "Docker contexts allow a client to select "
        "different daemon endpoints."
    )

    ledger = extract_claims(
        article
    )

    material = [
        claim
        for claim in ledger.claims
        if claim.material
    ]

    if not material:
        raise RuntimeError(
            "specimen produced no material claim"
        )

    claim = material[0]

    binding = bind_evidence_candidates(
        claim,
        [
            EvidenceSource(
                packet_id=11001,
                title="Docker context documentation",
                url=(
                    "https://example.invalid/"
                    "docker"
                ),
                excerpt=(
                    "Docker contexts allow a client "
                    "to select different daemon "
                    "endpoints."
                ),
                provider="documentation",
                relevance_passed=True,
            )
        ],
    )

    candidate = (
        binding.eligible_candidates[0]
    )

    verification = ClaimVerification(
        claim_id=claim.claim_id,
        claim_text=claim.text,
        claim_type=claim.claim_type,
        material=claim.material,
        verdict=(
            VerificationVerdict.SUPPORTED
        ),
        calibration=(
            CalibrationVerdict.PRECISE
        ),
        temporal_sensitivity=(
            TemporalSensitivity.NONE
        ),
        evidence=(
            VerifiedEvidence(
                packet_id=(
                    candidate.packet_id
                ),
                source_url=(
                    candidate.source_url
                ),
                excerpt_digest=(
                    candidate.excerpt_digest
                ),
            ),
        ),
        rationale=(
            "The bound evidence directly "
            "supports the claim."
        ),
    )

    article_verification = (
        build_article_verification(
            ledger.article_digest,
            [claim.claim_id],
            [verification],
        )
    )

    return build_reviewed_article_artifact(
        article_text=article,
        claim_ledger=ledger,
        evidence_sets=[binding],
        article_verification=(
            article_verification
        ),
        repair_history=[],
        provenance=ReviewProvenance(
            extractor_version=(
                ledger.extractor_version
            ),
            evidence_binder_version=(
                "anarchi.editorial-evidence.v1"
            ),
            verifier_contract_version=(
                "anarchi.editorial-verifier.v1"
            ),
            verifier_adapter_version=(
                "anarchi."
                "editorial-verifier-adapter.v1"
            ),
            verifier_model=(
                "granite4:tiny-h"
            ),
            verifier_run_id=(
                "visual-specimen-run-001"
            ),
        ),
    )


class EditorialVisualRequestTests(
    unittest.TestCase
):
    def test_version_is_stable(self):
        self.assertEqual(
            EDITORIAL_VISUAL_REQUEST_VERSION,
            "anarchi.editorial-visual-request.v1",
        )

    def test_reviewed_schema_binding_is_preserved(self):
        artifact = specimen_artifact()

        request = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.DECORATIVE
            ),
            visual_instruction=(
                "Create a non-factual abstract "
                "illustration."
            ),
        )

        self.assertEqual(
            request.reviewed_article_binding.schema_version,
            REVIEW_ARTIFACT_VERSION,
        )

    def test_clean_review_may_emit_decorative_request(self):
        artifact = specimen_artifact()

        request = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.DECORATIVE
            ),
            visual_instruction=(
                "Create an abstract visual metaphor "
                "without factual labels."
            ),
        )

        self.assertEqual(
            validate_request(
                request,
                artifact,
            ),
            (),
        )

    def test_conceptual_request_may_have_no_claim_binding(self):
        artifact = specimen_artifact()

        request = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.CONCEPTUAL
            ),
            visual_instruction=(
                "Represent endpoint selection "
                "conceptually without numeric or "
                "factual annotation."
            ),
        )

        self.assertEqual(
            request.bound_claim_ids,
            (),
        )

    def test_explanatory_requires_material_claim_binding(self):
        artifact = specimen_artifact()

        with self.assertRaises(
            ValueError
        ):
            build_editorial_visual_request(
                artifact=artifact,
                visual_purpose=(
                    VisualPurpose.EXPLANATORY
                ),
                visual_instruction=(
                    "Explain the relationship."
                ),
            )

    def test_factual_requires_material_claim_binding(self):
        artifact = specimen_artifact()

        with self.assertRaises(
            ValueError
        ):
            build_editorial_visual_request(
                artifact=artifact,
                visual_purpose=(
                    VisualPurpose.FACTUAL
                ),
                visual_instruction=(
                    "Render the factual relationship."
                ),
            )

    def test_factual_accepts_reviewed_material_claim(self):
        artifact = specimen_artifact()

        request = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.FACTUAL
            ),
            visual_instruction=(
                "Diagram the reviewed relationship "
                "without adding labels or facts not "
                "present in the reviewed claim."
            ),
            bound_claim_ids=(
                artifact.material_claim_ids
            ),
        )

        self.assertEqual(
            validate_request(
                request,
                artifact,
            ),
            (),
        )
        self.assertTrue(
            request.requires_semantic_visual_validation
        )

    def test_unknown_claim_binding_is_rejected(self):
        artifact = specimen_artifact()

        with self.assertRaises(
            ValueError
        ):
            build_editorial_visual_request(
                artifact=artifact,
                visual_purpose=(
                    VisualPurpose.FACTUAL
                ),
                visual_instruction=(
                    "Render a factual diagram."
                ),
                bound_claim_ids=(
                    "claim-does-not-exist",
                ),
            )

    def test_request_preserves_artifact_digest_exactly(self):
        artifact = specimen_artifact()

        request = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.DECORATIVE
            ),
            visual_instruction=(
                "Create an abstract illustration."
            ),
        )

        self.assertEqual(
            request.reviewed_article_binding.artifact_digest,
            artifact.artifact_digest,
        )

        self.assertEqual(
            len(
                request.reviewed_article_binding.artifact_digest
            ),
            64,
        )

        self.assertNotIn(
            ":",
            request.reviewed_article_binding.artifact_digest,
        )

    def test_tampered_artifact_binding_is_rejected(self):
        artifact = specimen_artifact()

        request = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.DECORATIVE
            ),
            visual_instruction=(
                "Create an abstract illustration."
            ),
        )

        tampered_binding = replace(
            request.reviewed_article_binding,
            artifact_digest=(
                "f" * 64
            ),
        )

        tampered = replace(
            request,
            reviewed_article_binding=(
                tampered_binding
            ),
        )

        errors = validate_request(
            tampered,
            artifact,
        )

        self.assertTrue(
            any(
                "artifact digest binding mismatch"
                in error
                for error in errors
            )
        )

    def test_request_cannot_introduce_claims(self):
        artifact = specimen_artifact()

        request = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.DECORATIVE
            ),
            visual_instruction=(
                "Create an abstract illustration."
            ),
        )

        constraints = replace(
            request.representation_constraints,
            may_introduce_new_claims=True,
        )

        mutated = replace(
            request,
            representation_constraints=(
                constraints
            ),
        )

        errors = validate_request(
            mutated,
            artifact,
        )

        self.assertTrue(
            any(
                "introduce new claims"
                in error
                for error in errors
            )
        )

    def test_request_cannot_strengthen_claims(self):
        artifact = specimen_artifact()

        request = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.DECORATIVE
            ),
            visual_instruction=(
                "Create an abstract illustration."
            ),
        )

        constraints = replace(
            request.representation_constraints,
            may_strengthen_claims=True,
        )

        mutated = replace(
            request,
            representation_constraints=(
                constraints
            ),
        )

        errors = validate_request(
            mutated,
            artifact,
        )

        self.assertTrue(
            any(
                "strengthen reviewed claims"
                in error
                for error in errors
            )
        )

    def test_request_has_zero_authority(self):
        artifact = specimen_artifact()

        request = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.FACTUAL
            ),
            visual_instruction=(
                "Render the reviewed relationship."
            ),
            bound_claim_ids=(
                artifact.material_claim_ids
            ),
        )

        self.assertEqual(
            request.authority_state,
            "REQUEST_ONLY",
        )
        self.assertEqual(
            request.evidentiary_authority,
            "NONE",
        )
        self.assertEqual(
            request.human_approval,
            "NONE",
        )
        self.assertEqual(
            request.publication_authority,
            "NONE",
        )

        self.assertFalse(
            request.grants_execution
        )
        self.assertFalse(
            request.grants_human_approval
        )
        self.assertFalse(
            request.grants_publication
        )
        self.assertFalse(
            request.grants_evidentiary_authority
        )

    def test_request_identity_is_deterministic(self):
        artifact = specimen_artifact()

        first = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.FACTUAL
            ),
            visual_instruction=(
                "Render the reviewed relationship."
            ),
            bound_claim_ids=(
                artifact.material_claim_ids
            ),
        )

        second = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.FACTUAL
            ),
            visual_instruction=(
                "Render the reviewed relationship."
            ),
            bound_claim_ids=(
                artifact.material_claim_ids
            ),
        )

        self.assertEqual(
            first.request_id,
            second.request_id,
        )
        self.assertEqual(
            first.request_digest,
            second.request_digest,
        )

    def test_instruction_change_changes_identity(self):
        artifact = specimen_artifact()

        first = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.DECORATIVE
            ),
            visual_instruction="First direction.",
        )

        second = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.DECORATIVE
            ),
            visual_instruction="Second direction.",
        )

        self.assertNotEqual(
            first.request_id,
            second.request_id,
        )
        self.assertNotEqual(
            first.request_digest,
            second.request_digest,
        )


if __name__ == "__main__":
    unittest.main()
