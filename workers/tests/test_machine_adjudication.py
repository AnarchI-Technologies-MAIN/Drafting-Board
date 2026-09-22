"""Focused tests for deterministic machine adjudication."""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from workers.blog_loop.machine_adjudication import (
    LOCAL_BUCKET_STATE,
    MACHINE_ADJUDICATION_VERSION,
    MACHINE_HOLD,
    MACHINE_PASS,
    adjudicate_reviewed_artifact,
    validate_machine_receipt,
)


@dataclass(frozen=True)
class FakeFracture:
    claim_id: str


@dataclass(frozen=True)
class FakeVerification:
    fractures: tuple[FakeFracture, ...]


@dataclass(frozen=True)
class FakeReviewedArtifact:
    artifact_digest: str
    text_review_passed: bool
    article_verification: FakeVerification
    human_adjudication_permitted: bool = False
    publication_permitted: bool = False


class MachineAdjudicationTests(unittest.TestCase):

    def make_artifact(
        self,
        *,
        passed: bool,
        fractures: tuple[str, ...] = (),
    ) -> FakeReviewedArtifact:
        return FakeReviewedArtifact(
            artifact_digest="sha256:" + ("a" * 64),
            text_review_passed=passed,
            article_verification=FakeVerification(
                fractures=tuple(
                    FakeFracture(claim_id=claim_id)
                    for claim_id in fractures
                )
            ),
        )

    def test_passed_artifact_gets_machine_pass(self) -> None:
        result = adjudicate_reviewed_artifact(
            self.make_artifact(passed=True)
        )

        self.assertEqual(result.disposition, MACHINE_PASS)
        self.assertEqual(result.artifact_digest, "sha256:" + ("a" * 64))
        self.assertEqual(result.fracture_claim_ids, ())
        self.assertEqual(
            result.bucket["bucket_state"],
            LOCAL_BUCKET_STATE,
        )
        self.assertEqual(
            result.bucket["human_adjudication_authority"],
            "NONE",
        )
        self.assertEqual(
            result.bucket["publication_authority"],
            "NONE",
        )

    def test_failed_artifact_gets_machine_hold(self) -> None:
        result = adjudicate_reviewed_artifact(
            self.make_artifact(
                passed=False,
                fractures=("claim-001", "claim-002"),
            )
        )

        self.assertEqual(result.disposition, MACHINE_HOLD)
        self.assertEqual(
            result.fracture_claim_ids,
            ("claim-001", "claim-002"),
        )
        self.assertEqual(
            result.bucket["bucket_state"],
            LOCAL_BUCKET_STATE,
        )

    def test_receipt_is_valid(self) -> None:
        result = adjudicate_reviewed_artifact(
            self.make_artifact(passed=True)
        )

        self.assertEqual(
            validate_machine_receipt(result.receipt),
            (),
        )

    def test_receipt_is_bound_to_artifact_digest(self) -> None:
        result = adjudicate_reviewed_artifact(
            self.make_artifact(passed=True)
        )

        self.assertEqual(
            result.receipt["artifact_digest"],
            result.artifact_digest,
        )

    def test_receipt_digest_detects_tampering(self) -> None:
        result = adjudicate_reviewed_artifact(
            self.make_artifact(passed=True)
        )

        tampered = dict(result.receipt)
        tampered["artifact_digest"] = "sha256:" + ("b" * 64)

        errors = validate_machine_receipt(tampered)

        self.assertIn("receipt_digest mismatch", errors)

    def test_machine_stage_grants_no_publication_authority(self) -> None:
        result = adjudicate_reviewed_artifact(
            self.make_artifact(passed=True)
        )

        self.assertFalse(result.publication_permitted)
        self.assertEqual(
            result.receipt["publication_authority"],
            "NONE",
        )

    def test_machine_stage_does_not_grant_human_authority_to_artifact(
        self,
    ) -> None:
        artifact = self.make_artifact(passed=True)

        self.assertFalse(artifact.human_adjudication_permitted)

        result = adjudicate_reviewed_artifact(artifact)

        self.assertTrue(result.human_adjudication_permitted)
        self.assertEqual(
            result.bucket["human_adjudication_authority"],
            "NONE",
        )

    def test_schema_version_is_stable(self) -> None:
        result = adjudicate_reviewed_artifact(
            self.make_artifact(passed=True)
        )

        self.assertEqual(
            result.schema_version,
            MACHINE_ADJUDICATION_VERSION,
        )
        self.assertEqual(
            result.receipt["schema_version"],
            MACHINE_ADJUDICATION_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
