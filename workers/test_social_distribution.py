from copy import deepcopy
from datetime import date, timedelta
import unittest

from test_editorial_visual_request import (
    specimen_artifact,
)

from social_distribution import (
    CAMPAIGN_HORIZON_VERSION,
    SOCIAL_DISTRIBUTION_EXPERT_VERSION,
    WEEKLY_PACKAGE_VERSION,
    SocialDistributionFailure,
    build_campaign_horizon,
    build_weekly_package,
    digest,
    validate_campaign_horizon,
    validate_weekly_package,
)


CAMPAIGN = (
    "campaign_anarchi_social_specimen"
)

PROFILE_DIGEST = (
    "7" * 64
)


def slot_for(
    artifact,
    *,
    timestamp,
    platform="FACEBOOK",
    format_name="POST",
    hook="PROBLEM_FIRST",
):
    return {
        "scheduled_at": timestamp,
        "platform": platform,
        "format": format_name,
        "platform_profile_version": 1,
        "platform_profile_digest": (
            PROFILE_DIGEST
        ),
        "content_role": "EDUCATIONAL",
        "hook_posture": hook,
        "caption_posture": (
            "CONCISE_EDUCATIONAL"
        ),
        "cta_posture": "SOFT",
        "visual_purpose": "FACTUAL",
        "claim_bindings": [
            {
                "artifact_digest": (
                    artifact.artifact_digest
                ),
                "claim_ids": list(
                    artifact.material_claim_ids
                ),
            }
        ],
    }


def package_for(
    week_index,
    *,
    revision=1,
    supersedes=None,
    hook="PROBLEM_FIRST",
):
    artifact = specimen_artifact()

    start = (
        date(
            2026,
            9,
            7,
        )
        + timedelta(
            days=7
            * (
                week_index
                - 1
            )
        )
    )

    timestamp = (
        start.isoformat()
        + "T10:00:00-05:00"
    )

    return build_weekly_package(
        artifacts=[
            artifact
        ],
        campaign_id=CAMPAIGN,
        campaign_objective=(
            "Introduce AnarchI problem-solving "
            "and verification capabilities."
        ),
        audience_segment=(
            "technical founders and operators"
        ),
        week_index=week_index,
        window_start=(
            start.isoformat()
        ),
        slots=[
            slot_for(
                artifact,
                timestamp=timestamp,
                hook=hook,
            )
        ],
        revision=revision,
        supersedes_package_digest=(
            supersedes
        ),
    )


def horizon_specimen():
    packages = [
        package_for(
            week
        )
        for week in range(
            1,
            9,
        )
    ]

    return (
        packages,
        build_campaign_horizon(
            packages
        ),
    )


class SocialDistributionTests(
    unittest.TestCase
):
    def test_versions_are_stable(self):
        self.assertEqual(
            WEEKLY_PACKAGE_VERSION,
            (
                "anarchi.weekly-campaign-"
                "package-proposal.v1"
            ),
        )

        self.assertEqual(
            CAMPAIGN_HORIZON_VERSION,
            (
                "anarchi.social-distribution-"
                "horizon.v1"
            ),
        )

        self.assertEqual(
            SOCIAL_DISTRIBUTION_EXPERT_VERSION,
            (
                "anarchi.social-distribution-"
                "expert.v1"
            ),
        )

    def test_weekly_package_validates(self):
        artifact = specimen_artifact()

        package = package_for(
            1
        )

        validated = (
            validate_weekly_package(
                package,
                artifacts=[
                    artifact
                ],
            )
        )

        self.assertEqual(
            validated,
            package,
        )

    def test_weekly_package_is_exactly_seven_days(self):
        package = package_for(
            1
        )

        start = date.fromisoformat(
            package[
                "window_start"
            ]
        )

        end = date.fromisoformat(
            package[
                "window_end"
            ]
        )

        self.assertEqual(
            (
                end
                - start
            ).days,
            6,
        )

    def test_week_one_is_ready_for_adjudication(self):
        package = package_for(
            1
        )

        self.assertEqual(
            package[
                "planning_resolution"
            ],
            "READY_FOR_ADJUDICATION",
        )

    def test_weeks_two_and_three_are_materialization_ready(self):
        self.assertEqual(
            package_for(
                2
            )[
                "planning_resolution"
            ],
            "MATERIALIZATION_READY",
        )

        self.assertEqual(
            package_for(
                3
            )[
                "planning_resolution"
            ],
            "MATERIALIZATION_READY",
        )

    def test_weeks_four_through_eight_are_structured_intent(self):
        for week in range(
            4,
            9,
        ):
            self.assertEqual(
                package_for(
                    week
                )[
                    "planning_resolution"
                ],
                "STRUCTURED_INTENT",
            )

    def test_package_has_zero_authority(self):
        package = package_for(
            1
        )

        self.assertEqual(
            package[
                "authority_state"
            ],
            "PACKAGE_PROPOSAL_ONLY",
        )

        self.assertEqual(
            package[
                "factual_authority"
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

    def test_slot_binds_only_reviewed_material_claims(self):
        artifact = specimen_artifact()

        bad_slot = slot_for(
            artifact,
            timestamp=(
                "2026-09-07"
                "T10:00:00-05:00"
            ),
        )

        bad_slot[
            "claim_bindings"
        ][0][
            "claim_ids"
        ] = [
            "claim-not-reviewed"
        ]

        with self.assertRaises(
            SocialDistributionFailure
        ):
            build_weekly_package(
                artifacts=[
                    artifact
                ],
                campaign_id=CAMPAIGN,
                campaign_objective=(
                    "specimen"
                ),
                audience_segment=(
                    "specimen"
                ),
                week_index=1,
                window_start=(
                    "2026-09-07"
                ),
                slots=[
                    bad_slot
                ],
            )

    def test_slot_outside_package_window_fails(self):
        artifact = specimen_artifact()

        with self.assertRaises(
            SocialDistributionFailure
        ):
            build_weekly_package(
                artifacts=[
                    artifact
                ],
                campaign_id=CAMPAIGN,
                campaign_objective=(
                    "specimen"
                ),
                audience_segment=(
                    "specimen"
                ),
                week_index=1,
                window_start=(
                    "2026-09-07"
                ),
                slots=[
                    slot_for(
                        artifact,
                        timestamp=(
                            "2026-09-14"
                            "T10:00:00-05:00"
                        ),
                    )
                ],
            )

    def test_platform_format_pair_is_enforced(self):
        artifact = specimen_artifact()

        with self.assertRaises(
            SocialDistributionFailure
        ):
            build_weekly_package(
                artifacts=[
                    artifact
                ],
                campaign_id=CAMPAIGN,
                campaign_objective=(
                    "specimen"
                ),
                audience_segment=(
                    "specimen"
                ),
                week_index=1,
                window_start=(
                    "2026-09-07"
                ),
                slots=[
                    slot_for(
                        artifact,
                        timestamp=(
                            "2026-09-07"
                            "T10:00:00-05:00"
                        ),
                        platform="TIKTOK",
                        format_name="CAROUSEL",
                    )
                ],
            )

    def test_final_copy_cannot_be_smuggled_into_slot(self):
        artifact = specimen_artifact()

        package = package_for(
            1
        )

        tampered = deepcopy(
            package
        )

        tampered[
            "distribution_slots"
        ][0][
            "caption_text"
        ] = (
            "Unreviewed final copy."
        )

        tampered.pop(
            "package_digest"
        )

        tampered[
            "package_digest"
        ] = digest(
            tampered
        )

        with self.assertRaises(
            SocialDistributionFailure
        ):
            validate_weekly_package(
                tampered,
                artifacts=[
                    artifact
                ],
            )

    def test_authority_escalation_fails(self):
        artifact = specimen_artifact()

        package = package_for(
            1
        )

        tampered = deepcopy(
            package
        )

        tampered[
            "publication_authority"
        ] = "GRANTED"

        tampered.pop(
            "package_digest"
        )

        tampered[
            "package_digest"
        ] = digest(
            tampered
        )

        with self.assertRaises(
            SocialDistributionFailure
        ):
            validate_weekly_package(
                tampered,
                artifacts=[
                    artifact
                ],
            )

    def test_replanning_creates_new_digest_and_supersedes_old(self):
        original = package_for(
            4
        )

        revised = package_for(
            4,
            revision=2,
            supersedes=(
                original[
                    "package_digest"
                ]
            ),
            hook="INSIGHT_FIRST",
        )

        self.assertNotEqual(
            revised[
                "package_digest"
            ],
            original[
                "package_digest"
            ],
        )

        self.assertEqual(
            revised[
                "supersedes_package_digest"
            ],
            original[
                "package_digest"
            ],
        )

        self.assertEqual(
            original[
                "revision"
            ],
            1,
        )

        self.assertEqual(
            revised[
                "revision"
            ],
            2,
        )

    def test_revision_two_requires_superseded_digest(self):
        with self.assertRaises(
            SocialDistributionFailure
        ):
            package_for(
                4,
                revision=2,
                supersedes=None,
            )

    def test_eight_week_horizon_validates(self):
        packages, horizon = (
            horizon_specimen()
        )

        validated = (
            validate_campaign_horizon(
                horizon,
                packages=packages,
            )
        )

        self.assertEqual(
            validated,
            horizon,
        )

        self.assertEqual(
            horizon[
                "horizon_weeks"
            ],
            8,
        )

    def test_horizon_has_zero_authority(self):
        _, horizon = (
            horizon_specimen()
        )

        self.assertEqual(
            horizon[
                "authority_state"
            ],
            "PLANNING_ONLY",
        )

        self.assertEqual(
            horizon[
                "factual_authority"
            ],
            "NONE",
        )

        self.assertEqual(
            horizon[
                "human_approval"
            ],
            "NONE",
        )

        self.assertEqual(
            horizon[
                "publication_authority"
            ],
            "NONE",
        )

    def test_horizon_requires_exactly_eight_weeks(self):
        packages = [
            package_for(
                week
            )
            for week in range(
                1,
                8,
            )
        ]

        with self.assertRaises(
            SocialDistributionFailure
        ):
            build_campaign_horizon(
                packages
            )

    def test_horizon_rejects_noncontiguous_window(self):
        packages = [
            package_for(
                week
            )
            for week in range(
                1,
                9,
            )
        ]

        broken = deepcopy(
            packages[
                4
            ]
        )

        broken[
            "window_start"
        ] = "2026-10-12"

        broken[
            "window_end"
        ] = "2026-10-18"

        broken.pop(
            "package_digest"
        )

        broken[
            "package_digest"
        ] = digest(
            broken
        )

        packages[
            4
        ] = broken

        with self.assertRaises(
            SocialDistributionFailure
        ):
            build_campaign_horizon(
                packages
            )

    def test_horizon_binds_exact_package_digests(self):
        packages, horizon = (
            horizon_specimen()
        )

        tampered = deepcopy(
            packages
        )

        replacement = package_for(
            8,
            revision=2,
            supersedes=(
                packages[
                    7
                ][
                    "package_digest"
                ]
            ),
            hook="INSIGHT_FIRST",
        )

        tampered[
            7
        ] = replacement

        with self.assertRaises(
            SocialDistributionFailure
        ):
            validate_campaign_horizon(
                horizon,
                packages=tampered,
            )

    def test_horizon_states_planning_law(self):
        _, horizon = (
            horizon_specimen()
        )

        self.assertEqual(
            horizon[
                "planning_law"
            ][
                "past"
            ],
            "EVIDENCE",
        )

        self.assertEqual(
            horizon[
                "planning_law"
            ][
                "future"
            ],
            "PROPOSAL",
        )

        self.assertEqual(
            horizon[
                "planning_law"
            ][
                "replanning"
            ],
            (
                "NEW_DIGEST_REQUIRES_"
                "FRESH_ADJUDICATION"
            ),
        )

    def test_resealed_slot_identity_tamper_fails(self):
        artifact = specimen_artifact()

        package = package_for(
            1
        )

        tampered = deepcopy(
            package
        )

        tampered[
            "distribution_slots"
        ][0][
            "slot_id"
        ] = "social_slot_counterfeit"

        tampered.pop(
            "package_digest"
        )

        tampered[
            "package_digest"
        ] = digest(
            tampered
        )

        with self.assertRaises(
            SocialDistributionFailure
        ):
            validate_weekly_package(
                tampered,
                artifacts=[
                    artifact
                ],
            )

    def test_resealed_package_identity_tamper_fails(self):
        artifact = specimen_artifact()

        package = package_for(
            1
        )

        tampered = deepcopy(
            package
        )

        tampered[
            "package_id"
        ] = "campaign_week_counterfeit"

        tampered.pop(
            "package_digest"
        )

        tampered[
            "package_digest"
        ] = digest(
            tampered
        )

        with self.assertRaises(
            SocialDistributionFailure
        ):
            validate_weekly_package(
                tampered,
                artifacts=[
                    artifact
                ],
            )

    def test_resealed_schedule_change_requires_new_slot_identity(self):
        artifact = specimen_artifact()

        package = package_for(
            1
        )

        tampered = deepcopy(
            package
        )

        tampered[
            "distribution_slots"
        ][0][
            "scheduled_at"
        ] = (
            "2026-09-08"
            "T10:00:00-05:00"
        )

        tampered.pop(
            "package_digest"
        )

        tampered[
            "package_digest"
        ] = digest(
            tampered
        )

        with self.assertRaises(
            SocialDistributionFailure
        ):
            validate_weekly_package(
                tampered,
                artifacts=[
                    artifact
                ],
            )

    def test_horizon_rejects_resealed_final_copy_smuggling(self):
        packages = [
            package_for(
                week
            )
            for week in range(
                1,
                9,
            )
        ]

        tampered = deepcopy(
            packages[
                3
            ]
        )

        tampered[
            "distribution_slots"
        ][0][
            "caption_text"
        ] = (
            "Counterfeit final copy."
        )

        tampered.pop(
            "package_digest"
        )

        tampered[
            "package_digest"
        ] = digest(
            tampered
        )

        packages[
            3
        ] = tampered

        with self.assertRaises(
            SocialDistributionFailure
        ):
            build_campaign_horizon(
                packages
            )

    def test_horizon_rejects_counterfeit_package_identity(self):
        packages = [
            package_for(
                week
            )
            for week in range(
                1,
                9,
            )
        ]

        tampered = deepcopy(
            packages[
                5
            ]
        )

        tampered[
            "package_id"
        ] = (
            "campaign_week_counterfeit"
        )

        tampered.pop(
            "package_digest"
        )

        tampered[
            "package_digest"
        ] = digest(
            tampered
        )

        packages[
            5
        ] = tampered

        with self.assertRaises(
            SocialDistributionFailure
        ):
            build_campaign_horizon(
                packages
            )


if __name__ == "__main__":
    unittest.main()
