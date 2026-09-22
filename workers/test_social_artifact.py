from copy import deepcopy
import unittest

from test_editorial_visual_request import (
    specimen_artifact,
)

from test_social_distribution import (
    package_for,
)

from social_artifact import (
    MATERIALIZATION_REQUEST_VERSION,
    SOCIAL_ARTIFACT_DRAFT_VERSION,
    SocialArtifactFailure,
    build_materialization_request,
    build_social_artifact_draft,
    digest,
    validate_materialization_request,
    validate_social_artifact_draft,
)


def specimen_request(
    week=1,
):
    artifact = specimen_artifact()

    package = package_for(
        week
    )

    slot = package[
        "distribution_slots"
    ][0]

    request = (
        build_materialization_request(
            package=package,
            artifacts=[
                artifact
            ],
            slot_id=slot[
                "slot_id"
            ],
        )
    )

    return (
        artifact,
        package,
        request,
    )


def specimen_copy():
    return {
        "headline": (
            "A deterministic system "
            "should know what it can prove."
        ),
        "body": (
            "Reviewed claims can be packaged "
            "for distribution without granting "
            "the planning layer factual authority."
        ),
        "cta": "Learn more.",
        "alt_text": (
            "Editorial verification workflow."
        ),
        "destination": (
            "https://anarchi.example/"
        ),
    }


class SocialArtifactTests(
    unittest.TestCase
):
    def test_versions_are_stable(self):
        self.assertEqual(
            MATERIALIZATION_REQUEST_VERSION,
            (
                "anarchi.social-artifact-"
                "materialization-request.v1"
            ),
        )

        self.assertEqual(
            SOCIAL_ARTIFACT_DRAFT_VERSION,
            (
                "anarchi.social-artifact-draft.v1"
            ),
        )

    def test_week_one_slot_emits_request(self):
        artifact, package, request = (
            specimen_request(
                1
            )
        )

        validated = (
            validate_materialization_request(
                request,
                package=package,
                artifacts=[
                    artifact
                ],
            )
        )

        self.assertEqual(
            validated,
            request,
        )

    def test_week_two_slot_emits_request(self):
        specimen_request(
            2
        )

    def test_structured_intent_week_is_not_materializable(self):
        artifact = specimen_artifact()

        package = package_for(
            4
        )

        slot = package[
            "distribution_slots"
        ][0]

        with self.assertRaises(
            SocialArtifactFailure
        ):
            build_materialization_request(
                package=package,
                artifacts=[
                    artifact
                ],
                slot_id=slot[
                    "slot_id"
                ],
            )

    def test_unknown_slot_fails(self):
        artifact = specimen_artifact()

        package = package_for(
            1
        )

        with self.assertRaises(
            SocialArtifactFailure
        ):
            build_materialization_request(
                package=package,
                artifacts=[
                    artifact
                ],
                slot_id=(
                    "social_slot_unknown"
                ),
            )

    def test_request_has_zero_authority(self):
        artifact, package, request = (
            specimen_request()
        )

        self.assertEqual(
            request[
                "authority_state"
            ],
            "MATERIALIZATION_REQUEST_ONLY",
        )

        self.assertEqual(
            request[
                "factual_authority"
            ],
            "NONE",
        )

        self.assertEqual(
            request[
                "human_approval"
            ],
            "NONE",
        )

        self.assertEqual(
            request[
                "publication_authority"
            ],
            "NONE",
        )

    def test_request_requires_atomic_review(self):
        artifact, package, request = (
            specimen_request()
        )

        self.assertTrue(
            request[
                "generation_constraints"
            ][
                "atomic_review_required"
            ]
        )

    def test_draft_materializes_copy(self):
        artifact, package, request = (
            specimen_request()
        )

        draft = (
            build_social_artifact_draft(
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=specimen_copy(),
            )
        )

        validated = (
            validate_social_artifact_draft(
                draft,
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
            )
        )

        self.assertEqual(
            validated,
            draft,
        )

    def test_draft_is_deterministic(self):
        artifact, package, request = (
            specimen_request()
        )

        first = (
            build_social_artifact_draft(
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=specimen_copy(),
            )
        )

        second = (
            build_social_artifact_draft(
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=specimen_copy(),
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_copy_change_changes_draft_identity(self):
        artifact, package, request = (
            specimen_request()
        )

        first_copy = (
            specimen_copy()
        )

        second_copy = (
            specimen_copy()
        )

        second_copy[
            "headline"
        ] = (
            "Different headline."
        )

        first = (
            build_social_artifact_draft(
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=first_copy,
            )
        )

        second = (
            build_social_artifact_draft(
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=second_copy,
            )
        )

        self.assertNotEqual(
            first[
                "draft_id"
            ],
            second[
                "draft_id"
            ],
        )

        self.assertNotEqual(
            first[
                "draft_digest"
            ],
            second[
                "draft_digest"
            ],
        )

    def test_draft_requires_atomic_review(self):
        artifact, package, request = (
            specimen_request()
        )

        draft = (
            build_social_artifact_draft(
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=specimen_copy(),
            )
        )

        self.assertEqual(
            draft[
                "review_state"
            ],
            "ATOMIC_REVIEW_REQUIRED",
        )

    def test_draft_does_not_claim_visual_completion(self):
        artifact, package, request = (
            specimen_request()
        )

        draft = (
            build_social_artifact_draft(
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=specimen_copy(),
            )
        )

        self.assertEqual(
            draft[
                "visual_state"
            ],
            "NOT_ATTACHED",
        )

    def test_draft_has_zero_authority(self):
        artifact, package, request = (
            specimen_request()
        )

        draft = (
            build_social_artifact_draft(
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=specimen_copy(),
            )
        )

        self.assertEqual(
            draft[
                "authority_state"
            ],
            "DRAFT_ONLY",
        )

        self.assertEqual(
            draft[
                "factual_authority"
            ],
            "NONE",
        )

        self.assertEqual(
            draft[
                "human_approval"
            ],
            "NONE",
        )

        self.assertEqual(
            draft[
                "publication_authority"
            ],
            "NONE",
        )

    def test_resealed_draft_id_tamper_fails(self):
        artifact, package, request = (
            specimen_request()
        )

        draft = (
            build_social_artifact_draft(
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=specimen_copy(),
            )
        )

        tampered = deepcopy(
            draft
        )

        tampered[
            "draft_id"
        ] = "social_draft_counterfeit"

        tampered.pop(
            "draft_digest"
        )

        tampered[
            "draft_digest"
        ] = digest(
            tampered
        )

        with self.assertRaises(
            SocialArtifactFailure
        ):
            validate_social_artifact_draft(
                tampered,
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
            )

    def test_resealed_review_state_escalation_fails(self):
        artifact, package, request = (
            specimen_request()
        )

        draft = (
            build_social_artifact_draft(
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=specimen_copy(),
            )
        )

        tampered = deepcopy(
            draft
        )

        tampered[
            "review_state"
        ] = "REVIEWED"

        tampered.pop(
            "draft_digest"
        )

        tampered[
            "draft_digest"
        ] = digest(
            tampered
        )

        with self.assertRaises(
            SocialArtifactFailure
        ):
            validate_social_artifact_draft(
                tampered,
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
            )

    def test_resealed_publication_escalation_fails(self):
        artifact, package, request = (
            specimen_request()
        )

        draft = (
            build_social_artifact_draft(
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=specimen_copy(),
            )
        )

        tampered = deepcopy(
            draft
        )

        tampered[
            "publication_authority"
        ] = "GRANTED"

        tampered.pop(
            "draft_digest"
        )

        tampered[
            "draft_digest"
        ] = digest(
            tampered
        )

        with self.assertRaises(
            SocialArtifactFailure
        ):
            validate_social_artifact_draft(
                tampered,
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
            )

    def test_request_tamper_fails(self):
        artifact, package, request = (
            specimen_request()
        )

        tampered = deepcopy(
            request
        )

        tampered[
            "slot_binding"
        ][
            "platform"
        ] = "INSTAGRAM"

        tampered.pop(
            "request_digest"
        )

        tampered[
            "request_digest"
        ] = digest(
            tampered
        )

        with self.assertRaises(
            SocialArtifactFailure
        ):
            validate_materialization_request(
                tampered,
                package=package,
                artifacts=[
                    artifact
                ],
            )

    def test_counterfeit_resealed_request_cannot_materialize_draft(self):
        artifact, package, request = (
            specimen_request()
        )

        counterfeit = deepcopy(
            request
        )

        counterfeit[
            "campaign_binding"
        ][
            "campaign_id"
        ] = "campaign_counterfeit"

        counterfeit.pop(
            "request_digest"
        )

        counterfeit[
            "request_digest"
        ] = digest(
            counterfeit
        )

        with self.assertRaises(
            SocialArtifactFailure
        ):
            build_social_artifact_draft(
                request=counterfeit,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=specimen_copy(),
            )

    def test_counterfeit_slot_request_cannot_materialize_draft(self):
        artifact, package, request = (
            specimen_request()
        )

        counterfeit = deepcopy(
            request
        )

        counterfeit[
            "slot_binding"
        ][
            "slot_id"
        ] = "social_slot_counterfeit"

        counterfeit.pop(
            "request_digest"
        )

        counterfeit[
            "request_digest"
        ] = digest(
            counterfeit
        )

        with self.assertRaises(
            SocialArtifactFailure
        ):
            build_social_artifact_draft(
                request=counterfeit,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=specimen_copy(),
            )

    def test_counterfeit_truth_binding_cannot_materialize_draft(self):
        artifact, package, request = (
            specimen_request()
        )

        counterfeit = deepcopy(
            request
        )

        counterfeit[
            "allowed_truth_bindings"
        ][0][
            "claim_ids"
        ] = [
            "claim-counterfeit"
        ]

        counterfeit.pop(
            "request_digest"
        )

        counterfeit[
            "request_digest"
        ] = digest(
            counterfeit
        )

        with self.assertRaises(
            SocialArtifactFailure
        ):
            build_social_artifact_draft(
                request=counterfeit,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=specimen_copy(),
            )

    def test_draft_validation_rejects_foreign_request_ancestry(self):
        artifact, package, request = (
            specimen_request()
        )

        draft = (
            build_social_artifact_draft(
                request=request,
                package=package,
                artifacts=[
                    artifact
                ],
                copy=specimen_copy(),
            )
        )

        foreign = deepcopy(
            request
        )

        foreign[
            "campaign_binding"
        ][
            "package_id"
        ] = "campaign_week_foreign"

        foreign.pop(
            "request_digest"
        )

        foreign[
            "request_digest"
        ] = digest(
            foreign
        )

        with self.assertRaises(
            SocialArtifactFailure
        ):
            validate_social_artifact_draft(
                draft,
                request=foreign,
                package=package,
                artifacts=[
                    artifact
                ],
            )


if __name__ == "__main__":
    unittest.main()
