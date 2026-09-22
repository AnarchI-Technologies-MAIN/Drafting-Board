from copy import deepcopy
import unittest

from test_social_visual_envelope import (
    specimen,
)

from social_visual_transport import (
    SOCIAL_VISUAL_TRANSPORT_VERSION,
    SocialVisualTransportFailure,
    build_social_visual_transport,
    validate_social_visual_transport,
)


def transport_specimen():
    (
        source,
        package,
        request,
        draft,
        reviewed,
        envelope,
    ) = specimen()

    transport = (
        build_social_visual_transport(
            envelope=envelope,
            reviewed=reviewed,
            draft=draft,
            request=request,
            package=package,
            source_artifacts=[
                source
            ],
        )
    )

    return (
        source,
        package,
        request,
        draft,
        reviewed,
        envelope,
        transport,
    )


class SocialVisualTransportTests(
    unittest.TestCase
):
    def test_version_is_stable(self):
        self.assertEqual(
            SOCIAL_VISUAL_TRANSPORT_VERSION,
            (
                "anarchi.social-visual-"
                "transport-package.v1"
            ),
        )

    def test_canonical_transport_validates(self):
        (
            source,
            package,
            request,
            draft,
            reviewed,
            envelope,
            transport,
        ) = transport_specimen()

        self.assertEqual(
            validate_social_visual_transport(
                transport,
                envelope=envelope,
                reviewed=reviewed,
                draft=draft,
                request=request,
                package=package,
                source_artifacts=[
                    source
                ],
            ),
            transport,
        )

    def test_social_ancestry_is_present(self):
        *_, transport = transport_specimen()

        ancestry = transport[
            "social_visual_envelope"
        ][
            "ancestry"
        ]

        for field in (
            "reviewed_social_digest",
            "draft_digest",
            "materialization_request_digest",
            "campaign_package_digest",
            "slot_id",
            "reviewed_core_artifact_digest",
        ):
            self.assertIn(
                field,
                ancestry,
            )

    def test_inner_editorial_package_is_embedded(self):
        *_, transport = transport_specimen()

        self.assertEqual(
            transport[
                "inner_editorial_package"
            ][
                "schema"
            ],
            "anarchi.editorial-visual-package.v1",
        )

    def test_inner_digest_binding_is_exact(self):
        *_, transport = transport_specimen()

        self.assertEqual(
            transport[
                "inner_editorial_package_digest"
            ],
            transport[
                "inner_editorial_package"
            ][
                "package_digest"
            ],
        )

    def test_inner_package_substitution_fails(self):
        (
            source,
            package,
            request,
            draft,
            reviewed,
            envelope,
            transport,
        ) = transport_specimen()

        foreign = deepcopy(
            transport
        )

        foreign[
            "inner_editorial_package"
        ][
            "handoff"
        ][
            "visual_instruction"
        ] = "Foreign visual instruction."

        with self.assertRaises(
            SocialVisualTransportFailure
        ):
            validate_social_visual_transport(
                foreign,
                envelope=envelope,
                reviewed=reviewed,
                draft=draft,
                request=request,
                package=package,
                source_artifacts=[
                    source
                ],
            )

    def test_social_ancestry_tamper_fails(self):
        (
            source,
            package,
            request,
            draft,
            reviewed,
            envelope,
            transport,
        ) = transport_specimen()

        foreign = deepcopy(
            transport
        )

        foreign[
            "social_visual_envelope"
        ][
            "ancestry"
        ][
            "slot_id"
        ] = "social_slot_foreign"

        with self.assertRaises(
            SocialVisualTransportFailure
        ):
            validate_social_visual_transport(
                foreign,
                envelope=envelope,
                reviewed=reviewed,
                draft=draft,
                request=request,
                package=package,
                source_artifacts=[
                    source
                ],
            )

    def test_transport_digest_tamper_fails(self):
        (
            source,
            package,
            request,
            draft,
            reviewed,
            envelope,
            transport,
        ) = transport_specimen()

        foreign = deepcopy(
            transport
        )

        foreign[
            "transport_digest"
        ] = (
            "sha256:"
            + "0" * 64
        )

        with self.assertRaises(
            SocialVisualTransportFailure
        ):
            validate_social_visual_transport(
                foreign,
                envelope=envelope,
                reviewed=reviewed,
                draft=draft,
                request=request,
                package=package,
                source_artifacts=[
                    source
                ],
            )

    def test_transport_has_zero_authority(self):
        *_, transport = transport_specimen()

        self.assertEqual(
            transport[
                "authority_state"
            ],
            "TRANSPORT_ONLY",
        )

        for field in (
            "evidentiary_authority",
            "factual_authority",
            "human_approval",
            "publication_authority",
        ):
            self.assertEqual(
                transport[
                    field
                ],
                "NONE",
            )


if __name__ == "__main__":
    unittest.main()
