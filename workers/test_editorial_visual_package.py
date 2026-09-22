import unittest
from copy import deepcopy

from test_editorial_visual_request import (
    specimen_artifact,
)

from editorial_visual_request import (
    VisualPurpose,
    build_editorial_visual_request,
)

from editorial_visual_package import (
    EDITORIAL_VISUAL_PACKAGE_VERSION,
    build_package,
    validate_package,
)


class EditorialVisualPackageTests(
    unittest.TestCase
):
    def factual_specimen(self):
        artifact = specimen_artifact()

        request = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.FACTUAL
            ),
            visual_instruction=(
                "Diagram only the reviewed "
                "relationship."
            ),
            bound_claim_ids=(
                artifact.material_claim_ids
            ),
        )

        package = build_package(
            artifact=artifact,
            request=request,
        )

        return (
            artifact,
            request,
            package,
        )

    def test_version_is_stable(self):
        self.assertEqual(
            EDITORIAL_VISUAL_PACKAGE_VERSION,
            "anarchi.editorial-visual-package.v1",
        )

    def test_clean_factual_package_validates(self):
        artifact, request, package = (
            self.factual_specimen()
        )

        self.assertEqual(
            validate_package(
                package,
                artifact=artifact,
                request=request,
            ),
            (),
        )

    def test_reviewed_article_text_is_exact(self):
        artifact, _, package = (
            self.factual_specimen()
        )

        self.assertEqual(
            package[
                "reviewed_context"
            ][
                "article_text"
            ],
            artifact.article_text,
        )

    def test_only_bound_claims_are_projected(self):
        artifact, request, package = (
            self.factual_specimen()
        )

        ids = tuple(
            item[
                "claim_id"
            ]
            for item in package[
                "reviewed_context"
            ][
                "bound_claims"
            ]
        )

        self.assertEqual(
            ids,
            request.bound_claim_ids,
        )

        self.assertEqual(
            ids,
            artifact.material_claim_ids,
        )

    def test_claim_text_is_exact(self):
        artifact, _, package = (
            self.factual_specimen()
        )

        projected = package[
            "reviewed_context"
        ][
            "bound_claims"
        ][0]

        source_claim = [
            claim
            for claim in artifact.claim_ledger.claims
            if claim.claim_id
            == projected[
                "claim_id"
            ]
        ][0]

        self.assertEqual(
            projected[
                "claim_text"
            ],
            source_claim.text,
        )

    def test_verifier_disposition_is_projected(self):
        artifact, _, package = (
            self.factual_specimen()
        )

        projected = package[
            "reviewed_context"
        ][
            "bound_claims"
        ][0]

        source = [
            item
            for item
            in artifact.article_verification.claims
            if item.claim_id
            == projected[
                "claim_id"
            ]
        ][0]

        self.assertEqual(
            projected[
                "verification"
            ][
                "verdict"
            ],
            source.verdict.value,
        )

        self.assertEqual(
            projected[
                "verification"
            ][
                "calibration"
            ],
            source.calibration.value,
        )

        self.assertEqual(
            projected[
                "verification"
            ][
                "acceptable"
            ],
            source.acceptable,
        )

    def test_relied_evidence_identity_is_projected(self):
        artifact, _, package = (
            self.factual_specimen()
        )

        projected = package[
            "reviewed_context"
        ][
            "bound_claims"
        ][0][
            "verification"
        ][
            "relied_on_evidence"
        ]

        source = artifact.article_verification.claims[
            0
        ].evidence

        self.assertEqual(
            len(
                projected
            ),
            len(
                source
            ),
        )

        self.assertEqual(
            projected[
                0
            ][
                "packet_id"
            ],
            source[
                0
            ].packet_id,
        )

        self.assertEqual(
            projected[
                0
            ][
                "excerpt_digest"
            ],
            source[
                0
            ].excerpt_digest,
        )

    def test_decorative_request_projects_no_claims(self):
        artifact = specimen_artifact()

        request = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.DECORATIVE
            ),
            visual_instruction=(
                "Create a decorative treatment "
                "without factual annotation."
            ),
        )

        package = build_package(
            artifact=artifact,
            request=request,
        )

        self.assertEqual(
            package[
                "reviewed_context"
            ][
                "bound_claims"
            ],
            [],
        )

        self.assertEqual(
            package[
                "reviewed_context"
            ][
                "article_text"
            ],
            artifact.article_text,
        )

    def test_tampered_claim_text_fails_validation(self):
        artifact, request, package = (
            self.factual_specimen()
        )

        tampered = deepcopy(
            package
        )

        tampered[
            "reviewed_context"
        ][
            "bound_claims"
        ][0][
            "claim_text"
        ] = "Invented stronger claim."

        errors = validate_package(
            tampered,
            artifact=artifact,
            request=request,
        )

        self.assertTrue(
            any(
                "claim projection changed"
                in error
                for error in errors
            )
        )

    def test_tampered_verdict_fails_validation(self):
        artifact, request, package = (
            self.factual_specimen()
        )

        tampered = deepcopy(
            package
        )

        tampered[
            "reviewed_context"
        ][
            "bound_claims"
        ][0][
            "verification"
        ][
            "verdict"
        ] = "CONTRADICTED"

        errors = validate_package(
            tampered,
            artifact=artifact,
            request=request,
        )

        self.assertTrue(
            any(
                "claim projection changed"
                in error
                for error in errors
            )
        )

    def test_package_digest_detects_tamper(self):
        artifact, request, package = (
            self.factual_specimen()
        )

        tampered = deepcopy(
            package
        )

        tampered[
            "reviewed_context"
        ][
            "article_text"
        ] = "Changed after sealing."

        errors = validate_package(
            tampered,
            artifact=artifact,
            request=request,
        )

        self.assertTrue(
            any(
                "package digest mismatch"
                in error
                for error in errors
            )
        )

    def test_package_has_zero_authority(self):
        _, _, package = (
            self.factual_specimen()
        )

        self.assertEqual(
            package[
                "authority_state"
            ],
            "TRANSPORT_ONLY",
        )

        self.assertEqual(
            package[
                "evidentiary_authority"
            ],
            "NONE",
        )

        self.assertEqual(
            package[
                "human_approval"
            ],
            "NONE",
        )

        self.assertEqual(
            package[
                "publication_authority"
            ],
            "NONE",
        )

    def test_package_identity_is_deterministic(self):
        artifact = specimen_artifact()

        request = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.FACTUAL
            ),
            visual_instruction=(
                "Diagram only the reviewed "
                "relationship."
            ),
            bound_claim_ids=(
                artifact.material_claim_ids
            ),
        )

        first = build_package(
            artifact=artifact,
            request=request,
        )

        second = build_package(
            artifact=artifact,
            request=request,
        )

        self.assertEqual(
            first[
                "package_digest"
            ],
            second[
                "package_digest"
            ],
        )


if __name__ == "__main__":
    unittest.main()
