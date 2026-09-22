import unittest
from copy import deepcopy

from test_editorial_visual_request import (
    specimen_artifact,
)

from editorial_visual_request import (
    VisualPurpose,
    build_editorial_visual_request,
)

from editorial_visual_transport import (
    EDITORIAL_VISUAL_HANDOFF_VERSION,
    build_handoff,
    from_transport_digest,
    to_transport_digest,
    validate_handoff,
)


class EditorialVisualTransportTests(
    unittest.TestCase
):
    def specimen(self):
        artifact = specimen_artifact()

        request = build_editorial_visual_request(
            artifact=artifact,
            visual_purpose=(
                VisualPurpose.FACTUAL
            ),
            visual_instruction=(
                "Diagram only the reviewed "
                "relationship without adding "
                "new factual content."
            ),
            bound_claim_ids=(
                artifact.material_claim_ids
            ),
        )

        return (
            artifact,
            request,
        )

    def test_version_is_stable(self):
        self.assertEqual(
            EDITORIAL_VISUAL_HANDOFF_VERSION,
            "anarchi.editorial-visual-handoff.v1",
        )

    def test_native_digest_normalizes(self):
        native = "a" * 64

        self.assertEqual(
            to_transport_digest(
                native
            ),
            "sha256:" + native,
        )

    def test_transport_digest_round_trips(self):
        native = "b" * 64

        transported = to_transport_digest(
            native
        )

        recovered = from_transport_digest(
            transported
        )

        self.assertEqual(
            recovered,
            native,
        )

    def test_double_normalization_is_rejected(self):
        canonical = (
            "sha256:"
            + "a" * 64
        )

        with self.assertRaises(
            ValueError
        ):
            to_transport_digest(
                canonical
            )

    def test_native_uppercase_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            to_transport_digest(
                "A" * 64
            )

    def test_native_whitespace_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            to_transport_digest(
                ("a" * 64)
                + " "
            )

    def test_transport_without_prefix_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            from_transport_digest(
                "a" * 64
            )

    def test_transport_wrong_prefix_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            from_transport_digest(
                "SHA256:"
                + "a" * 64
            )

    def test_transport_uppercase_hex_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            from_transport_digest(
                "sha256:"
                + "A" * 64
            )

    def test_transport_whitespace_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            from_transport_digest(
                "sha256:"
                + "a" * 64
                + " "
            )

    def test_clean_request_builds_valid_handoff(self):
        artifact, request = (
            self.specimen()
        )

        envelope = build_handoff(
            request,
            artifact,
        )

        self.assertEqual(
            validate_handoff(
                envelope,
                request,
                artifact,
            ),
            (),
        )

    def test_artifact_identity_survives_transport(self):
        artifact, request = (
            self.specimen()
        )

        envelope = build_handoff(
            request,
            artifact,
        )

        value = (
            envelope[
                "reviewed_article_binding"
            ][
                "artifact_digest"
            ]
        )

        self.assertEqual(
            from_transport_digest(
                value
            ),
            artifact.artifact_digest,
        )

    def test_article_identity_survives_transport(self):
        artifact, request = (
            self.specimen()
        )

        envelope = build_handoff(
            request,
            artifact,
        )

        value = (
            envelope[
                "reviewed_article_binding"
            ][
                "article_digest"
            ]
        )

        self.assertEqual(
            from_transport_digest(
                value
            ),
            artifact.article_digest,
        )

    def test_request_identity_survives_transport(self):
        artifact, request = (
            self.specimen()
        )

        envelope = build_handoff(
            request,
            artifact,
        )

        value = (
            envelope[
                "source_request_binding"
            ][
                "request_digest"
            ]
        )

        self.assertEqual(
            from_transport_digest(
                value
            ),
            request.request_digest,
        )

    def test_tampered_artifact_digest_is_rejected(self):
        artifact, request = (
            self.specimen()
        )

        envelope = build_handoff(
            request,
            artifact,
        )

        tampered = deepcopy(
            envelope
        )

        tampered[
            "reviewed_article_binding"
        ][
            "artifact_digest"
        ] = (
            "sha256:"
            + "f" * 64
        )

        errors = validate_handoff(
            tampered,
            request,
            artifact,
        )

        self.assertTrue(
            any(
                "artifact identity changed"
                in error
                for error in errors
            )
        )

    def test_tampered_claim_binding_is_rejected(self):
        artifact, request = (
            self.specimen()
        )

        envelope = build_handoff(
            request,
            artifact,
        )

        tampered = deepcopy(
            envelope
        )

        tampered[
            "bound_claim_ids"
        ] = [
            "claim-invented"
        ]

        errors = validate_handoff(
            tampered,
            request,
            artifact,
        )

        self.assertTrue(
            any(
                "transport changed field"
                in error
                for error in errors
            )
        )

    def test_tampered_instruction_is_rejected(self):
        artifact, request = (
            self.specimen()
        )

        envelope = build_handoff(
            request,
            artifact,
        )

        tampered = deepcopy(
            envelope
        )

        tampered[
            "visual_instruction"
        ] = (
            "Changed after sealing."
        )

        errors = validate_handoff(
            tampered,
            request,
            artifact,
        )

        self.assertTrue(
            any(
                "transport changed field"
                in error
                for error in errors
            )
        )

        self.assertTrue(
            any(
                "handoff digest mismatch"
                in error
                for error in errors
            )
        )

    def test_authority_remains_zero(self):
        artifact, request = (
            self.specimen()
        )

        envelope = build_handoff(
            request,
            artifact,
        )

        self.assertEqual(
            envelope[
                "authority_state"
            ],
            "REQUEST_ONLY",
        )

        self.assertEqual(
            envelope[
                "evidentiary_authority"
            ],
            "NONE",
        )

        self.assertEqual(
            envelope[
                "human_approval"
            ],
            "NONE",
        )

        self.assertEqual(
            envelope[
                "publication_authority"
            ],
            "NONE",
        )


if __name__ == "__main__":
    unittest.main()
