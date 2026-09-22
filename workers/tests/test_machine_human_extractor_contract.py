"""Contract tests for the real human-adjudication artifact extractor."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import workers.blog_loop.human_adjudication as human_module
from workers.blog_loop.machine_adjudication import (
    adjudicate_reviewed_artifact,
)
from workers.editorial_review_artifact import digest_payload


class HumanExtractorContractTests(unittest.TestCase):

    def make_artifact(self):
        return {
            "schema_version": "anarchi.reviewed-article.v1",
            "article_text": "Test article body.",
            "article_digest": "sha256:" + ("a" * 64),
            "gates": {
                "text_review_passed": True,
                "human_adjudication_permitted": False,
                "publication_permitted": False,
            },
        }

    def make_machine_sidecar(self, artifact_digest):
        artifact = SimpleNamespace(
            artifact_digest=artifact_digest,
            text_review_passed=True,
            article_verification=SimpleNamespace(fractures=()),
            human_adjudication_permitted=False,
            publication_permitted=False,
        )

        machine = adjudicate_reviewed_artifact(artifact)

        return {
            "schema_version": machine.schema_version,
            "artifact_digest": machine.artifact_digest,
            "disposition": machine.disposition,
            "fracture_claim_ids": list(machine.fracture_claim_ids),
            "receipt": machine.receipt,
            "bucket": machine.bucket,
            "human_adjudication_authority": "NONE",
            "publication_authority": "NONE",
        }

    def make_job(self):
        artifact = self.make_artifact()
        artifact_digest = digest_payload(artifact)

        return {
            "id": 999999,
            "state": "quality_hold",
            "body": artifact["article_text"],
            "quality": {
                "atomic_review": {
                    "text_review_passed": True,
                    "artifact_digest": artifact_digest,
                    "artifact": artifact,
                    "machine_adjudication": self.make_machine_sidecar(
                        artifact_digest
                    ),
                },
            },
        }

    def test_real_extractor_is_callable(self):
        self.assertTrue(
            callable(human_module._extract_review_artifact)
        )

    def test_valid_reviewed_artifact_with_machine_pass_is_accepted(self):
        job = self.make_job()

        artifact = human_module._extract_review_artifact(job)

        self.assertEqual(
            artifact["schema_version"],
            "anarchi.reviewed-article.v1",
        )

    def test_human_extractor_requires_machine_sidecar(self):
        job = self.make_job()

        del job["quality"]["atomic_review"]["machine_adjudication"]

        with self.assertRaises(ValueError):
            human_module._extract_review_artifact(job)

    def test_human_extractor_rejects_machine_artifact_digest_mismatch(self):
        job = self.make_job()

        job["quality"]["atomic_review"]["machine_adjudication"][
            "artifact_digest"
        ] = "sha256:" + ("b" * 64)

        with self.assertRaises(ValueError):
            human_module._extract_review_artifact(job)

    def test_human_extractor_rejects_machine_hold(self):
        job = self.make_job()

        job["quality"]["atomic_review"]["machine_adjudication"][
            "disposition"
        ] = "ADJUDICATED_HOLD"

        with self.assertRaises(ValueError):
            human_module._extract_review_artifact(job)

    def test_human_extractor_rejects_tampered_machine_receipt(self):
        job = self.make_job()

        job["quality"]["atomic_review"]["machine_adjudication"][
            "receipt"
        ]["artifact_digest"] = "sha256:" + ("b" * 64)

        with self.assertRaises(ValueError):
            human_module._extract_review_artifact(job)

    def test_human_extractor_rejects_invalid_machine_bucket(self):
        job = self.make_job()

        job["quality"]["atomic_review"]["machine_adjudication"][
            "bucket"
        ]["bucket_state"] = "INVALID"

        with self.assertRaises(ValueError):
            human_module._extract_review_artifact(job)

    def test_human_extractor_does_not_import_machine_module(self):
        with open(
            human_module.__file__,
            "r",
            encoding="utf-8",
        ) as handle:
            source = handle.read()

        try:
            self.assertNotIn(
                "from workers.blog_loop.machine_adjudication",
                source,
            )
            self.assertNotIn(
                "import workers.blog_loop.machine_adjudication",
                source,
            )
        finally:
            pass

    def test_artifact_digest_remains_bound_to_reviewed_artifact(self):
        job = self.make_job()

        artifact = human_module._extract_review_artifact(job)

        self.assertEqual(
            digest_payload(artifact),
            job["quality"]["atomic_review"]["artifact_digest"],
        )

    def test_machine_authority_remains_none(self):
        job = self.make_job()
        machine = job["quality"]["atomic_review"]["machine_adjudication"]

        self.assertEqual(
            machine["human_adjudication_authority"],
            "NONE",
        )

        self.assertEqual(
            machine["publication_authority"],
            "NONE",
        )


if __name__ == "__main__":
    unittest.main()

