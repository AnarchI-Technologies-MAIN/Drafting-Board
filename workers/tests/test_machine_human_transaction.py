"""Real human-adjudication transaction contract tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import workers.blog_loop.human_adjudication as human_module
from workers.blog_loop.machine_adjudication import adjudicate_reviewed_artifact
from workers.editorial_review_artifact import digest_payload


class FakeCursor:
    def __init__(self, job):
        self.job = job
        self.executed = []
        self.fetchone_values = []
        self.closed = False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

        normalized = " ".join(sql.split())

        if normalized.startswith("SELECT id, decision, artifact_digest, receipt_digest"):
            self.fetchone_values.append(None)

        elif normalized.startswith("INSERT INTO blogger_human_adjudications"):
            pass

        elif "UPDATE generation_queue" in normalized and "RETURNING" in normalized:
            self.fetchone_values.append({
                "id": self.job["id"],
                "state": "staged",
                "staged_at": "TEST",
            })

        elif "UPDATE generation_queue" in normalized:
            self.fetchone_values.append(None)

    def fetchone(self):
        if self.fetchone_values:
            return self.fetchone_values.pop(0)
        return None

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        return False


class FakeCursorReject(FakeCursor):
    pass


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        return False


class HumanTransactionTests(unittest.TestCase):
    def make_artifact(self):
        artifact = {
            "schema_version": "anarchi.reviewed-article.v1",
            "article_text": "Test article body.",
            "article_digest": "sha256:" + ("a" * 64),
            "gates": {
                "text_review_passed": True,
                "human_adjudication_permitted": False,
                "publication_permitted": False,
            },
        }
        return artifact

    def make_machine_sidecar(self, artifact_digest):
        reviewed = SimpleNamespace(
            artifact_digest=artifact_digest,
            text_review_passed=True,
            article_verification=SimpleNamespace(fractures=()),
            human_adjudication_permitted=False,
            publication_permitted=False,
        )
        machine = adjudicate_reviewed_artifact(reviewed)

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
            "id": 888888,
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

    def test_approved_human_decision_is_the_staging_transition(self):
        job = self.make_job()
        cursor = FakeCursor(job)
        connection = FakeConnection(cursor)

        with patch.object(
            human_module,
            "ensure_adjudication_schema",
        ), patch.object(
            human_module,
            "get_connection",
            return_value=connection,
        ), patch.object(
            human_module,
            "_load_job",
            return_value=job,
        ):
            result = human_module.adjudicate(
                job["id"],
                decision="APPROVED",
                reviewer="test-human",
                reason="approved by human adjudication",
            )

        self.assertEqual(result["status"], "STAGED")
        self.assertEqual(result["job_id"], job["id"])
        self.assertEqual(result["artifact_digest"], job["quality"]["atomic_review"]["artifact_digest"])
        self.assertTrue(connection.committed)

        statements = [
            " ".join(sql.split())
            for sql, _ in cursor.executed
        ]

        self.assertTrue(
            any(
                statement.startswith(
                    "INSERT INTO blogger_human_adjudications"
                )
                for statement in statements
            )
        )

        staging = [
            (sql, params)
            for sql, params in cursor.executed
            if "UPDATE generation_queue SET state='staged'" in " ".join(sql.split())
        ]

        self.assertEqual(len(staging), 1)
        self.assertEqual(staging[0][1][0], job["id"])
        self.assertEqual(
            staging[0][1][1],
            job["quality"]["atomic_review"]["artifact_digest"],
        )

    def test_rejected_human_decision_does_not_stage(self):
        job = self.make_job()
        cursor = FakeCursorReject(job)
        connection = FakeConnection(cursor)

        with patch.object(
            human_module,
            "ensure_adjudication_schema",
        ), patch.object(
            human_module,
            "get_connection",
            return_value=connection,
        ), patch.object(
            human_module,
            "_load_job",
            return_value=job,
        ):
            result = human_module.adjudicate(
                job["id"],
                decision="REJECTED",
                reviewer="test-human",
                reason="human rejected",
            )

        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(connection.committed)

        statements = [
            " ".join(sql.split())
            for sql, _ in cursor.executed
        ]

        self.assertTrue(
            any(
                statement.startswith(
                    "INSERT INTO blogger_human_adjudications"
                )
                for statement in statements
            )
        )

        self.assertFalse(
            any(
                "UPDATE generation_queue SET state='staged'"
                in statement
                for statement in statements
            )
        )

        self.assertTrue(
            any(
                statement.startswith(
                    "UPDATE generation_queue SET last_error="
                )
                for statement in statements
            )
        )

    def test_missing_machine_sidecar_blocks_before_human_receipt(self):
        job = self.make_job()
        del job["quality"]["atomic_review"]["machine_adjudication"]

        cursor = FakeCursor(job)
        connection = FakeConnection(cursor)

        with patch.object(
            human_module,
            "ensure_adjudication_schema",
        ), patch.object(
            human_module,
            "get_connection",
            return_value=connection,
        ), patch.object(
            human_module,
            "_load_job",
            return_value=job,
        ):
            with self.assertRaises(ValueError):
                human_module.adjudicate(
                    job["id"],
                    decision="APPROVED",
                    reviewer="test-human",
                    reason="should never reach staging",
                )

        statements = [
            " ".join(sql.split())
            for sql, _ in cursor.executed
        ]

        self.assertFalse(
            any(
                statement.startswith(
                    "INSERT INTO blogger_human_adjudications"
                )
                for statement in statements
            )
        )

        self.assertFalse(
            any(
                "UPDATE generation_queue SET state='staged'"
                in statement
                for statement in statements
            )
        )

        self.assertTrue(connection.rolled_back)

    def test_tampered_machine_receipt_blocks_before_human_receipt(self):
        job = self.make_job()

        machine = job["quality"]["atomic_review"]["machine_adjudication"]
        machine["receipt"]["artifact_digest"] = "sha256:" + ("b" * 64)

        cursor = FakeCursor(job)
        connection = FakeConnection(cursor)

        with patch.object(
            human_module,
            "ensure_adjudication_schema",
        ), patch.object(
            human_module,
            "get_connection",
            return_value=connection,
        ), patch.object(
            human_module,
            "_load_job",
            return_value=job,
        ):
            with self.assertRaises(ValueError):
                human_module.adjudicate(
                    job["id"],
                    decision="APPROVED",
                    reviewer="test-human",
                    reason="tampered receipt",
                )

        statements = [
            " ".join(sql.split())
            for sql, _ in cursor.executed
        ]

        self.assertFalse(
            any(
                statement.startswith(
                    "INSERT INTO blogger_human_adjudications"
                )
                for statement in statements
            )
        )

        self.assertFalse(
            any(
                "UPDATE generation_queue SET state='staged'"
                in statement
                for statement in statements
            )
        )

        self.assertTrue(connection.rolled_back)


if __name__ == "__main__":
    unittest.main()




