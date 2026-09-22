"""Focused real-handoff contract tests."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

from workers.blog_loop.machine_adjudication import (
    adjudicate_reviewed_artifact,
)


HUMAN_MODULE = (
    Path(__file__).resolve().parents[1]
    / "blog_loop"
    / "human_adjudication.py"
)


class MachineHumanRealHandoffTests(unittest.TestCase):

    def make_artifact(self, passed=True, fractures=()):
        verification = SimpleNamespace(
            fractures=tuple(
                SimpleNamespace(claim_id=claim_id)
                for claim_id in fractures
            )
        )

        return SimpleNamespace(
            artifact_digest="sha256:" + ("c" * 64),
            text_review_passed=passed,
            article_verification=verification,
            human_adjudication_permitted=False,
            publication_permitted=False,
        )

    def make_quality_payload(self):
        artifact = self.make_artifact()
        machine = adjudicate_reviewed_artifact(artifact)

        return {
            "passed": True,
            "atomic_review": {
                "attempted": True,
                "text_review_passed": True,
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
            },
        }

    def test_human_module_exists(self):
        self.assertTrue(HUMAN_MODULE.exists())

    def test_human_module_parses(self):
        source = HUMAN_MODULE.read_text(encoding="utf-8")
        ast.parse(source)

    def test_human_module_does_not_import_machine_module(self):
        source = HUMAN_MODULE.read_text(encoding="utf-8")

        self.assertNotIn(
            "from workers.blog_loop.machine_adjudication",
            source,
        )

        self.assertNotIn(
            "import workers.blog_loop.machine_adjudication",
            source,
        )

    def test_existing_atomic_review_contract_is_preserved(self):
        quality = self.make_quality_payload()
        atomic = quality["atomic_review"]

        required = (
            "attempted",
            "text_review_passed",
            "artifact_digest",
            "artifact",
            "fracture_claim_ids",
            "verifier_observations",
            "publication_authority",
            "human_adjudication_authority",
        )

        for field in required:
            self.assertIn(field, atomic)

    def test_machine_sidecar_is_additive(self):
        quality = self.make_quality_payload()
        atomic = quality["atomic_review"]

        self.assertIn("machine_adjudication", atomic)

        existing_fields = {
            "attempted",
            "text_review_passed",
            "artifact_digest",
            "artifact",
            "fracture_claim_ids",
            "verifier_observations",
            "publication_authority",
            "human_adjudication_authority",
        }

        self.assertTrue(
            existing_fields.issubset(set(atomic))
        )

    def test_quality_hold_contract_is_preserved(self):
        quality = self.make_quality_payload()

        job = {
            "id": 999999,
            "state": "quality_hold",
            "quality": quality,
        }

        self.assertEqual(
            job["state"],
            "quality_hold",
        )

        self.assertIn(
            "atomic_review",
            job["quality"],
        )

        self.assertIn(
            "machine_adjudication",
            job["quality"]["atomic_review"],
        )

    def test_machine_identity_is_bound_to_reviewed_artifact(self):
        quality = self.make_quality_payload()
        atomic = quality["atomic_review"]
        machine = atomic["machine_adjudication"]

        self.assertEqual(
            machine["artifact_digest"],
            atomic["artifact_digest"],
        )

        self.assertEqual(
            machine["receipt"]["artifact_digest"],
            atomic["artifact_digest"],
        )

        self.assertEqual(
            machine["bucket"]["artifact_digest"],
            atomic["artifact_digest"],
        )

    def test_machine_pass_remains_human_pending(self):
        quality = self.make_quality_payload()
        machine = quality["atomic_review"]["machine_adjudication"]

        self.assertEqual(
            machine["disposition"],
            "ADJUDICATED_PASS",
        )

        self.assertEqual(
            machine["bucket"]["bucket_state"],
            "MACHINE_ADJUDICATED_HUMAN_PENDING",
        )

        self.assertEqual(
            machine["bucket"]["human_adjudication_authority"],
            "NONE",
        )

        self.assertEqual(
            machine["bucket"]["publication_authority"],
            "NONE",
        )


if __name__ == "__main__":
    unittest.main()
