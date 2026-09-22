from copy import deepcopy
from dataclasses import replace
import unittest

from editorial_visual_request import (
    VisualPurpose,
)

from test_social_atomic_review import (
    reviewed_specimen,
)

from social_visual_envelope import (
    SOCIAL_VISUAL_ENVELOPE_VERSION,
    SocialVisualEnvelopeFailure,
    build_social_visual_envelope,
    validate_social_visual_envelope,
)


def specimen():
    (
        source,
        package,
        request,
        draft,
        case,
        reviewed,
    ) = reviewed_specimen()

    if reviewed is None:
        raise RuntimeError(
            "reviewed social specimen unavailable"
        )

    material_claim_ids = (
        reviewed.review_core.material_claim_ids
    )

    if not material_claim_ids:
        raise RuntimeError(
            "reviewed social specimen has no material claims"
        )

    envelope = (
        build_social_visual_envelope(
            reviewed=reviewed,
            draft=draft,
            request=request,
            package=package,
            source_artifacts=[
                source
            ],
            visual_purpose=(
                VisualPurpose.EXPLANATORY
            ),
            visual_instruction=(
                "Create an explanatory visual "
                "that represents only the reviewed "
                "social claim relationships."
            ),
            bound_claim_ids=(
                material_claim_ids
            ),
        )
    )

    return (
        source,
        package,
        request,
        draft,
        reviewed,
        envelope,
    )


class SocialVisualEnvelopeTests(
    unittest.TestCase
):
    def test_version_is_stable(self):
        self.assertEqual(
            SOCIAL_VISUAL_ENVELOPE_VERSION,
            "anarchi.social-visual-envelope.v1",
        )

    def test_canonical_reviewed_social_builds_envelope(self):
        (
            source,
            package,
            request,
            draft,
            reviewed,
            envelope,
        ) = specimen()

        self.assertEqual(
            validate_social_visual_envelope(
                envelope,
                reviewed=reviewed,
                draft=draft,
                request=request,
                package=package,
                source_artifacts=[
                    source
                ],
            ),
            envelope,
        )

    def test_envelope_preserves_reviewed_social_digest(self):
        _, _, _, _, reviewed, envelope = (
            specimen()
        )

        self.assertEqual(
            envelope.ancestry.reviewed_social_digest,
            reviewed.reviewed_social_digest,
        )

    def test_envelope_preserves_draft_identity(self):
        _, _, _, draft, _, envelope = (
            specimen()
        )

        self.assertEqual(
            envelope.ancestry.draft_id,
            draft[
                "draft_id"
            ],
        )

        self.assertEqual(
            envelope.ancestry.draft_digest,
            draft[
                "draft_digest"
            ],
        )

    def test_envelope_preserves_materialization_request_identity(self):
        _, _, request, _, _, envelope = (
            specimen()
        )

        self.assertEqual(
            envelope.ancestry.materialization_request_digest,
            request[
                "request_digest"
            ],
        )

    def test_envelope_preserves_campaign_package_identity(self):
        _, package, _, _, _, envelope = (
            specimen()
        )

        self.assertEqual(
            envelope.ancestry.campaign_package_digest,
            package[
                "package_digest"
            ],
        )

    def test_envelope_preserves_slot_identity(self):
        _, _, request, _, _, envelope = (
            specimen()
        )

        self.assertEqual(
            envelope.ancestry.slot_id,
            request[
                "slot_binding"
            ][
                "slot_id"
            ],
        )

    def test_envelope_preserves_review_core_identity(self):
        _, _, _, _, reviewed, envelope = (
            specimen()
        )

        self.assertEqual(
            envelope.ancestry.reviewed_core_artifact_digest,
            reviewed.review_core.artifact_digest,
        )

    def test_embedded_visual_request_binds_review_core(self):
        _, _, _, _, reviewed, envelope = (
            specimen()
        )

        self.assertEqual(
            (
                envelope.visual_request
                .reviewed_article_binding
                .artifact_digest
            ),
            reviewed.review_core.artifact_digest,
        )

        self.assertEqual(
            (
                envelope.visual_request
                .reviewed_article_binding
                .article_digest
            ),
            reviewed.review_core.article_digest,
        )

    def test_embedded_visual_request_identity_is_preserved(self):
        _, _, _, _, _, envelope = (
            specimen()
        )

        self.assertEqual(
            envelope.visual_request_id,
            envelope.visual_request.request_id,
        )

        self.assertEqual(
            envelope.visual_request_digest,
            envelope.visual_request.request_digest,
        )

    def test_envelope_has_zero_authority(self):
        _, _, _, _, _, envelope = (
            specimen()
        )

        self.assertEqual(
            envelope.authority_state,
            "REQUEST_ENVELOPE_ONLY",
        )

        self.assertEqual(
            envelope.evidentiary_authority,
            "NONE",
        )

        self.assertEqual(
            envelope.factual_authority,
            "NONE",
        )

        self.assertEqual(
            envelope.human_approval,
            "NONE",
        )

        self.assertEqual(
            envelope.publication_authority,
            "NONE",
        )

    def test_envelope_digest_is_deterministic(self):
        _, _, _, _, _, first = (
            specimen()
        )

        _, _, _, _, _, second = (
            specimen()
        )

        self.assertEqual(
            first.envelope_digest,
            second.envelope_digest,
        )

    def test_campaign_package_change_rejects_validation(self):
        (
            source,
            package,
            request,
            draft,
            reviewed,
            envelope,
        ) = specimen()

        foreign = deepcopy(
            package
        )

        foreign[
            "campaign_id"
        ] = "campaign_foreign"

        with self.assertRaises(
            SocialVisualEnvelopeFailure
        ):
            validate_social_visual_envelope(
                envelope,
                reviewed=reviewed,
                draft=draft,
                request=request,
                package=foreign,
                source_artifacts=[
                    source
                ],
            )

    def test_slot_change_rejects_validation(self):
        (
            source,
            package,
            request,
            draft,
            reviewed,
            envelope,
        ) = specimen()

        foreign_request = deepcopy(
            request
        )

        foreign_request[
            "slot_binding"
        ][
            "slot_id"
        ] = "social_slot_foreign"

        with self.assertRaises(
            SocialVisualEnvelopeFailure
        ):
            validate_social_visual_envelope(
                envelope,
                reviewed=reviewed,
                draft=draft,
                request=foreign_request,
                package=package,
                source_artifacts=[
                    source
                ],
            )

    def test_reviewed_social_digest_tamper_is_rejected(self):
        (
            source,
            package,
            request,
            draft,
            reviewed,
            envelope,
        ) = specimen()

        ancestry = replace(
            envelope.ancestry,
            reviewed_social_digest=(
                "0" * 64
            ),
        )

        tampered = replace(
            envelope,
            ancestry=ancestry,
        )

        with self.assertRaises(
            SocialVisualEnvelopeFailure
        ):
            validate_social_visual_envelope(
                tampered,
                reviewed=reviewed,
                draft=draft,
                request=request,
                package=package,
                source_artifacts=[
                    source
                ],
            )

    def test_review_core_binding_tamper_is_rejected(self):
        (
            source,
            package,
            request,
            draft,
            reviewed,
            envelope,
        ) = specimen()

        foreign_binding = replace(
            (
                envelope.visual_request
                .reviewed_article_binding
            ),
            artifact_digest=(
                "0" * 64
            ),
        )

        foreign_visual_request = replace(
            envelope.visual_request,
            reviewed_article_binding=(
                foreign_binding
            ),
        )

        tampered = replace(
            envelope,
            visual_request=(
                foreign_visual_request
            ),
        )

        with self.assertRaises(
            SocialVisualEnvelopeFailure
        ):
            validate_social_visual_envelope(
                tampered,
                reviewed=reviewed,
                draft=draft,
                request=request,
                package=package,
                source_artifacts=[
                    source
                ],
            )

    def test_visual_request_digest_substitution_is_rejected(self):
        (
            source,
            package,
            request,
            draft,
            reviewed,
            envelope,
        ) = specimen()

        tampered = replace(
            envelope,
            visual_request_digest=(
                "0" * 64
            ),
        )

        with self.assertRaises(
            SocialVisualEnvelopeFailure
        ):
            validate_social_visual_envelope(
                tampered,
                reviewed=reviewed,
                draft=draft,
                request=request,
                package=package,
                source_artifacts=[
                    source
                ],
            )

    def test_envelope_digest_tamper_is_rejected(self):
        (
            source,
            package,
            request,
            draft,
            reviewed,
            envelope,
        ) = specimen()

        tampered = replace(
            envelope,
            envelope_digest=(
                "0" * 64
            ),
        )

        with self.assertRaises(
            SocialVisualEnvelopeFailure
        ):
            validate_social_visual_envelope(
                tampered,
                reviewed=reviewed,
                draft=draft,
                request=request,
                package=package,
                source_artifacts=[
                    source
                ],
            )


if __name__ == "__main__":
    unittest.main()
