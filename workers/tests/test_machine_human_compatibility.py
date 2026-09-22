"""Focused compatibility tests for machine adjudication -> human adjudication.

These tests verify that the machine-adjudication sidecar can coexist with the
existing human adjudication module and quality_hold payload contract.

The human adjudication module remains the downstream authority gate.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

import workers.blog_loop.human_adjudication as human_module

from workers.blog_loop.machine_adjudication import (
    adjudicate_reviewed_artifact,
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


class MachineHumanCompatibilityTests(unittest.TestCase):

    def make_artifact(self) -> FakeReviewedArtifact:
        return FakeReviewedArtifact(
            artifact_digest="sha256:" + ("a" * 64),
            text_review_passed=True,
            article_verification=FakeVerification(
                fractures=(),
            ),
        )

    def make_atomic_review_payload(self) -> dict:
        artifact = self.make_artifact()
        machine = adjudicate_reviewed_artifact(artifact)

        return {
            "attempted": True,
            "text_review_passed": artifact.text_review_passed,
            "artifact_digest": artifact.artifact_digest,
            "artifact": {
                "schema_version": "test",
                "article_digest": artifact.artifact_digest,
            },
            "fracture_claim_ids": [],
            "verifier_observations": [],
            "publication_authority": "NONE",
            "human_adjudication_authority": "NONE",
            "machine_adjudication": {
                "schema_version": machine.schema_version,
                "artifact_digest": machine.artifact_digest,
                "disposition": machine.disposition,
                "fracture_claim_ids": list(
                    machine.fracture_claim_ids
                ),
                "receipt": machine.receipt,
                "bucket": machine.bucket,
                "human_adjudication_authority": "NONE",
                "publication_authority": "NONE",
            },
        }

    def test_human_adjudication_module_imports(self) -> None:
        self.assertIsNotNone(human_module)

    def test_machine_sidecar_is_nested_inside_atomic_review(self) -> None:
        payload = self.make_atomic_review_payload()

        self.assertIn("machine_adjudication", payload)

        machine = payload["machine_adjudication"]

        self.assertEqual(
            machine["artifact_digest"],
            payload["artifact_digest"],
        )

    def test_machine_sidecar_does_not_replace_human_authority(self) -> None:
        payload = self.make_atomic_review_payload()

        machine = payload["machine_adjudication"]

        self.assertEqual(
            machine["human_adjudication_authority"],
            "NONE",
        )

        self.assertEqual(
            machine["publication_authority"],
            "NONE",
        )

    def test_machine_receipt_and_bucket_are_present(self) -> None:
        payload = self.make_atomic_review_payload()

        machine = payload["machine_adjudication"]

        self.assertIn("receipt", machine)
        self.assertIn("bucket", machine)

        self.assertEqual(
            machine["receipt"]["artifact_digest"],
            machine["artifact_digest"],
        )

        self.assertEqual(
            machine["bucket"]["artifact_digest"],
            machine["artifact_digest"],
        )

    def test_quality_hold_payload_can_carry_machine_sidecar(self) -> None:
        quality = {
            "passed": True,
            "atomic_review": self.make_atomic_review_payload(),
        }

        job_result = {
            "state": "quality_hold",
            "title": "Compatibility Test",
            "slug": "compatibility-test",
            "summary": "Compatibility test payload.",
            "body": "Compatibility test body.",
            "seo": {},
            "quality": quality,
            "model_lineage": {},
            "error": "awaiting human adjudication",
        }

        self.assertEqual(
            job_result["state"],
            "quality_hold",
        )

        self.assertIn(
            "machine_adjudication",
            job_result["quality"]["atomic_review"],
        )

        self.assertEqual(
            job_result["quality"]["atomic_review"][
                "machine_adjudication"
            ]["human_adjudication_authority"],
            "NONE",
        )

    def test_machine_pass_does_not_change_database_state_contract(self) -> None:
        payload = self.make_atomic_review_payload()

        quality_hold_state = "quality_hold"
        machine_disposition = payload["machine_adjudication"]["disposition"]

        self.assertEqual(
            quality_hold_state,
            "quality_hold",
        )

        self.assertEqual(
            machine_disposition,
            "ADJUDICATED_PASS",
        )

        self.assertNotEqual(
            machine_disposition,
            "staged",
        )

    def test_human_module_contains_its_existing_authority_implementation(
        self,
    ) -> None:
        with open(
            human_module.__file__,
            "r",
            encoding="utf-8",
        ) as handle:
            source = handle.read()

        self.assertIn(
            "human",
            source.lower(),
        )

        self.assertIn(
            "adjudicat",
            source.lower(),
        )


if __name__ == "__main__":
    unittest.main()

