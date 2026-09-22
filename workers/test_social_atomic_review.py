from dataclasses import replace
from copy import deepcopy
import unittest

from editorial_claims import (
    article_digest,
)

from editorial_review_artifact import (
    ReviewProvenance,
)

from editorial_verifier import (
    CalibrationVerdict,
    ClaimVerification,
    TemporalSensitivity,
    VerificationVerdict,
    VerifiedEvidence,
)

from test_social_artifact import (
    specimen_request,
)

from social_artifact import (
    build_social_artifact_draft,
)

from social_atomic_review import (
    PROJECTION_VERSION,
    SOCIAL_REVIEW_CASE_VERSION,
    SOCIAL_REVIEWED_ARTIFACT_VERSION,
    SocialAtomicReviewFailure,
    build_reviewed_social_artifact,
    build_social_review_case,
    claim_field,
    digest,
    validate_reviewed_social_artifact,
    validate_social_review_case,
)


def social_case():
    artifact, package, request = (
        specimen_request()
    )

    copy = {
        "headline": (
            "Docker contexts can select "
            "different daemon endpoints."
        ),
        "body": (
            "Docker contexts allow a client "
            "to select different daemon endpoints."
        ),
        "cta": (
            "Learn more."
        ),
        "alt_text": (
            "Docker context configuration workflow."
        ),
        "destination": (
            "https://anarchi.example/"
        ),
    }

    draft = build_social_artifact_draft(
        request=request,
        package=package,
        artifacts=[
            artifact
        ],
        copy=copy,
    )

    case = build_social_review_case(
        draft=draft,
        request=request,
        package=package,
        artifacts=[
            artifact
        ],
    )

    return (
        artifact,
        package,
        request,
        draft,
        case,
    )


def synthetic_verifications(
    case,
):
    evidence_by_claim = {
        item.claim_id: item
        for item
        in case.evidence_sets
    }

    results = []

    for claim in case.claim_ledger.claims:
        evidence_set = evidence_by_claim[
            claim.claim_id
        ]

        eligible = [
            candidate
            for candidate
            in evidence_set.candidates
            if candidate.eligible
        ]

        evidence = tuple(
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
            )
            for candidate
            in eligible[:1]
        )

        if claim.material:
            if evidence:
                verdict = (
                    VerificationVerdict.SUPPORTED
                )

                rationale = (
                    "Synthetic contract specimen."
                )
            else:
                verdict = (
                    VerificationVerdict.INSUFFICIENT_EVIDENCE
                )

                rationale = (
                    "No eligible inherited evidence."
                )

            results.append(
                ClaimVerification(
                    claim_id=(
                        claim.claim_id
                    ),
                    claim_text=(
                        claim.text
                    ),
                    claim_type=(
                        claim.claim_type
                    ),
                    material=True,
                    verdict=(
                        verdict
                    ),
                    calibration=(
                        CalibrationVerdict.PRECISE
                    ),
                    temporal_sensitivity=(
                        TemporalSensitivity.NONE
                    ),
                    evidence=(
                        evidence
                        if verdict
                        == VerificationVerdict.SUPPORTED
                        else ()
                    ),
                    rationale=(
                        rationale
                    ),
                )
            )

            continue

        results.append(
            ClaimVerification(
                claim_id=(
                    claim.claim_id
                ),
                claim_text=(
                    claim.text
                ),
                claim_type=(
                    claim.claim_type
                ),
                material=False,
                verdict=(
                    VerificationVerdict.NON_FACTUAL
                ),
                calibration=(
                    CalibrationVerdict.PRECISE
                ),
                temporal_sensitivity=(
                    TemporalSensitivity.NONE
                ),
                evidence=(),
                rationale=(
                    "Synthetic non-material specimen."
                ),
            )
        )

    return tuple(
        results
    )


def all_material_supported(
    verifications,
):
    return all(
        (
            not item.material
            or item.verdict
            == VerificationVerdict.SUPPORTED
        )
        for item in verifications
    )


def provenance():
    return ReviewProvenance(
        extractor_version=(
            "anarchi.editorial-claims.v2"
        ),
        evidence_binder_version=(
            "anarchi.editorial-evidence.v1"
        ),
        verifier_contract_version=(
            "anarchi.editorial-verifier.v1"
        ),
        verifier_adapter_version=(
            "contract-specimen-no-model"
        ),
        verifier_model=(
            "NO_MODEL_CONTRACT_SPECIMEN"
        ),
        verifier_run_id=(
            "social-011y-r1-specimen"
        ),
    )


def reviewed_specimen():
    (
        source,
        package,
        request,
        draft,
        case,
    ) = social_case()

    verifications = (
        synthetic_verifications(
            case
        )
    )

    if not all_material_supported(
        verifications
    ):
        return (
            source,
            package,
            request,
            draft,
            case,
            None,
        )

    reviewed = (
        build_reviewed_social_artifact(
            case=case,
            claim_verifications=(
                verifications
            ),
            provenance=(
                provenance()
            ),
        )
    )

    return (
        source,
        package,
        request,
        draft,
        case,
        reviewed,
    )


class SocialAtomicReviewTests(
    unittest.TestCase
):
    def test_versions_are_stable(self):
        self.assertEqual(
            SOCIAL_REVIEW_CASE_VERSION,
            (
                "anarchi.social-atomic-"
                "review-case.v1"
            ),
        )

        self.assertEqual(
            SOCIAL_REVIEWED_ARTIFACT_VERSION,
            (
                "anarchi.reviewed-social-"
                "artifact.v1"
            ),
        )

        self.assertEqual(
            PROJECTION_VERSION,
            (
                "anarchi.social-review-"
                "projection.v1"
            ),
        )

    def test_case_uses_atomic_reviewer_native_digest(self):
        _, _, _, _, case = (
            social_case()
        )

        self.assertEqual(
            case.projection_digest,
            article_digest(
                case.projection_text
            ),
        )

        self.assertEqual(
            case.claim_ledger.article_digest,
            case.projection_digest,
        )

    def test_case_builds_from_canonical_draft(self):
        _, _, _, _, case = (
            social_case()
        )

        self.assertEqual(
            validate_social_review_case(
                case
            ),
            case,
        )

    def test_destination_is_not_in_projection(self):
        _, _, _, draft, case = (
            social_case()
        )

        self.assertNotIn(
            draft[
                "copy"
            ][
                "destination"
            ],
            case.projection_text,
        )

    def test_all_customer_language_fields_are_projected(self):
        _, _, _, _, case = (
            social_case()
        )

        self.assertEqual(
            [
                field.field_name
                for field
                in case.projection_fields
            ],
            [
                "headline",
                "body",
                "cta",
                "alt_text",
            ],
        )

    def test_claims_resolve_to_one_copy_field(self):
        _, _, _, _, case = (
            social_case()
        )

        for claim in case.claim_ledger.claims:
            owner = claim_field(
                claim,
                case.projection_fields,
            )

            self.assertIn(
                owner,
                {
                    "headline",
                    "body",
                    "cta",
                    "alt_text",
                },
            )

    def test_source_verdict_is_not_in_review_case(self):
        _, _, _, _, case = (
            social_case()
        )

        self.assertFalse(
            hasattr(
                case,
                "source_verdict",
            )
        )

        self.assertFalse(
            hasattr(
                case,
                "verification",
            )
        )

    def test_only_relied_source_evidence_enters_pool(self):
        source, _, _, _, case = (
            social_case()
        )

        relied = {
            (
                evidence.packet_id,
                evidence.source_url,
                evidence.excerpt_digest,
            )
            for verification
            in source.article_verification.claims
            for evidence
            in verification.evidence
        }

        observed = {
            (
                candidate.packet_id,
                candidate.source_url,
                candidate.excerpt_digest,
            )
            for evidence_set
            in case.evidence_sets
            for candidate
            in evidence_set.candidates
        }

        self.assertTrue(
            observed.issubset(
                relied
            )
        )

    def test_evidence_candidate_does_not_mean_support(self):
        _, _, _, _, case = (
            social_case()
        )

        self.assertFalse(
            hasattr(
                case,
                "article_verification",
            )
        )

    def test_projection_digest_is_deterministic(self):
        _, _, _, _, first = (
            social_case()
        )

        _, _, _, _, second = (
            social_case()
        )

        self.assertEqual(
            first.projection_digest,
            second.projection_digest,
        )

    def test_contradicted_material_claim_blocks_review(self):
        _, _, _, _, case = (
            social_case()
        )

        verifications = list(
            synthetic_verifications(
                case
            )
        )

        material_index = next(
            index
            for index, item
            in enumerate(
                verifications
            )
            if item.material
        )

        verifications[
            material_index
        ] = replace(
            verifications[
                material_index
            ],
            verdict=(
                VerificationVerdict.CONTRADICTED
            ),
            evidence=(),
            rationale=(
                "Synthetic contradiction."
            ),
        )

        with self.assertRaises(
            SocialAtomicReviewFailure
        ):
            build_reviewed_social_artifact(
                case=case,
                claim_verifications=(
                    verifications
                ),
                provenance=(
                    provenance()
                ),
            )

    def test_missing_material_claim_blocks_review(self):
        _, _, _, _, case = (
            social_case()
        )

        verifications = [
            item
            for item
            in synthetic_verifications(
                case
            )
            if not item.material
        ]

        with self.assertRaises(
            SocialAtomicReviewFailure
        ):
            build_reviewed_social_artifact(
                case=case,
                claim_verifications=(
                    verifications
                ),
                provenance=(
                    provenance()
                ),
            )

    def test_reviewed_social_artifact_has_zero_authority(self):
        (
            _,
            _,
            _,
            _,
            _,
            reviewed,
        ) = reviewed_specimen()

        if reviewed is None:
            self.skipTest(
                "specimen has a material social claim "
                "without eligible inherited evidence"
            )

        self.assertEqual(
            reviewed.authority_state,
            "TEXT_REVIEWED_ONLY",
        )

        self.assertEqual(
            reviewed.factual_authority,
            "NONE",
        )

        self.assertEqual(
            reviewed.human_approval,
            "NONE",
        )

        self.assertEqual(
            reviewed.publication_authority,
            "NONE",
        )

    def test_reviewed_social_validates_against_exact_ancestry(self):
        (
            source,
            package,
            request,
            draft,
            _,
            reviewed,
        ) = reviewed_specimen()

        if reviewed is None:
            self.skipTest(
                "specimen has a material social claim "
                "without eligible inherited evidence"
            )

        self.assertEqual(
            validate_reviewed_social_artifact(
                reviewed,
                draft=draft,
                request=request,
                package=package,
                source_artifacts=[
                    source
                ],
            ),
            reviewed,
        )

    def test_reviewed_social_rejects_foreign_package_ancestry(self):
        (
            source,
            package,
            request,
            draft,
            _,
            reviewed,
        ) = reviewed_specimen()

        if reviewed is None:
            self.skipTest(
                "specimen has a material social claim "
                "without eligible inherited evidence"
            )

        foreign_package = deepcopy(
            package
        )

        foreign_package[
            "campaign_id"
        ] = "campaign_foreign"

        with self.assertRaises(
            SocialAtomicReviewFailure
        ):
            validate_reviewed_social_artifact(
                reviewed,
                draft=draft,
                request=request,
                package=foreign_package,
                source_artifacts=[
                    source
                ],
            )

    def test_reviewed_social_digest_detects_tamper(self):
        (
            source,
            package,
            request,
            draft,
            _,
            reviewed,
        ) = reviewed_specimen()

        if reviewed is None:
            self.skipTest(
                "specimen has a material social claim "
                "without eligible inherited evidence"
            )

        tampered = replace(
            reviewed,
            slot_id=(
                "social_slot_counterfeit"
            ),
        )

        with self.assertRaises(
            SocialAtomicReviewFailure
        ):
            validate_reviewed_social_artifact(
                tampered,
                draft=draft,
                request=request,
                package=package,
                source_artifacts=[
                    source
                ],
            )


if __name__ == "__main__":
    unittest.main()
