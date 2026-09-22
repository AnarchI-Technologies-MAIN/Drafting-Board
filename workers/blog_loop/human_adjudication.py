"""Blogger-only human adjudication authority gate.

This module is intentionally downstream of machine review.

It does not modify reviewed article content.
It does not grant authority to the ReviewedArticleArtifact.
It records an explicit human decision against the exact reviewed artifact
digest and, only on approval, transitions that generation job from
quality_hold to staged.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from db import get_connection
from editorial_review_artifact import digest_payload


ADJUDICATION_SCHEMA = "anarchi.blogger-human-adjudication.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def receipt_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()


def ensure_adjudication_schema() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS blogger_human_adjudications (
                    id BIGSERIAL PRIMARY KEY,
                    generation_job_id BIGINT NOT NULL,
                    artifact_digest TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    receipt_digest TEXT NOT NULL UNIQUE,
                    receipt JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT blogger_human_adjudications_decision_check
                        CHECK (decision IN ('APPROVED', 'REJECTED')),
                    CONSTRAINT blogger_human_adjudications_job_unique
                        UNIQUE (generation_job_id)
                )
                """
            )


def _load_job(cur, job_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT
            id,
            state,
            title,
            slug,
            summary,
            body,
            seo,
            quality,
            model_lineage,
            last_error,
            staged_at,
            published_at
        FROM generation_queue
        WHERE id=%s
        """,
        (job_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _extract_review_artifact(job: dict[str, Any]) -> dict[str, Any]:
    quality = job.get("quality") or {}
    atomic_review = quality.get("atomic_review") or {}
    artifact = atomic_review.get("artifact")

    if not isinstance(artifact, dict):
        raise ValueError("generation job has no reviewed article artifact")

    if atomic_review.get("text_review_passed") is not True:
        raise ValueError("generation job does not have a passing text review")

    if artifact.get("schema_version") != "anarchi.reviewed-article.v1":
        raise ValueError("reviewed article artifact schema mismatch")

    if artifact.get("gates", {}).get("text_review_passed") is not True:
        raise ValueError("reviewed article artifact text gate is not passed")

    if artifact.get("gates", {}).get("human_adjudication_permitted") is not False:
        raise ValueError("reviewed article artifact authority contract changed")

    if artifact.get("gates", {}).get("publication_permitted") is not False:
        raise ValueError("reviewed article artifact publication contract changed")

    expected_digest = atomic_review.get("artifact_digest")
    if not expected_digest:
        raise ValueError("generation job has no atomic review artifact digest")

    actual_digest = digest_payload(artifact)

    if actual_digest != expected_digest:
        raise ValueError("stored reviewed artifact digest mismatch")

    machine = atomic_review.get("machine_adjudication")

    if not isinstance(machine, dict):
        raise ValueError("generation job has no machine adjudication")

    if machine.get("schema_version") != "anarchi.blog-machine-adjudication.v1":
        raise ValueError("machine adjudication schema mismatch")

    if machine.get("artifact_digest") != expected_digest:
        raise ValueError("machine adjudication artifact digest mismatch")

    if machine.get("disposition") != "ADJUDICATED_PASS":
        raise ValueError("machine adjudication did not pass")

    if machine.get("human_adjudication_authority") != "NONE":
        raise ValueError("machine adjudication unexpectedly grants human authority")

    if machine.get("publication_authority") != "NONE":
        raise ValueError("machine adjudication unexpectedly grants publication authority")

    receipt = machine.get("receipt")

    if not isinstance(receipt, dict):
        raise ValueError("machine adjudication has no receipt")

    required_receipt_fields = (
        "schema_version",
        "artifact_digest",
        "disposition",
        "fracture_claim_ids",
        "human_adjudication_authority",
        "publication_authority",
        "receipt_digest",
    )

    missing_receipt_fields = [
        field for field in required_receipt_fields
        if field not in receipt
    ]

    if missing_receipt_fields:
        raise ValueError(
            "machine receipt missing fields: "
            + ", ".join(missing_receipt_fields)
        )

    if receipt["schema_version"] != "anarchi.blog-machine-adjudication.v1":
        raise ValueError("machine receipt schema mismatch")

    if receipt["artifact_digest"] != expected_digest:
        raise ValueError("machine receipt artifact digest mismatch")

    if receipt["disposition"] != "ADJUDICATED_PASS":
        raise ValueError("machine receipt disposition is not a pass")

    if not isinstance(receipt["fracture_claim_ids"], list):
        raise ValueError("machine receipt fracture_claim_ids must be a list")

    if receipt["human_adjudication_authority"] != "NONE":
        raise ValueError("machine receipt unexpectedly grants human authority")

    if receipt["publication_authority"] != "NONE":
        raise ValueError("machine receipt unexpectedly grants publication authority")

    receipt_payload = {
        "schema_version": receipt["schema_version"],
        "artifact_digest": receipt["artifact_digest"],
        "disposition": receipt["disposition"],
        "fracture_claim_ids": receipt["fracture_claim_ids"],
        "human_adjudication_authority": receipt["human_adjudication_authority"],
        "publication_authority": receipt["publication_authority"],
    }

    expected_machine_receipt_digest = (
        "sha256:"
        + hashlib.sha256(
            canonical_json(receipt_payload).encode("utf-8")
        ).hexdigest()
    )

    if receipt["receipt_digest"] != expected_machine_receipt_digest:
        raise ValueError("machine receipt digest mismatch")

    bucket = machine.get("bucket")

    if not isinstance(bucket, dict):
        raise ValueError("machine adjudication has no bucket")

    if bucket.get("bucket_state") != "MACHINE_ADJUDICATED_HUMAN_PENDING":
        raise ValueError("machine adjudication bucket is not human-pending")

    if bucket.get("artifact_digest") != expected_digest:
        raise ValueError("machine bucket artifact digest mismatch")

    if bucket.get("human_adjudication_authority") != "NONE":
        raise ValueError("machine bucket unexpectedly grants human authority")

    if bucket.get("publication_authority") != "NONE":
        raise ValueError("machine bucket unexpectedly grants publication authority")

    return artifact


def inspect_job(job_id: int) -> dict[str, Any]:
    ensure_adjudication_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            job = _load_job(cur, job_id)

            if not job:
                raise ValueError(f"generation job {job_id} does not exist")

            artifact = _extract_review_artifact(job)

            cur.execute(
                """
                SELECT
                    id,
                    decision,
                    reviewer,
                    reason,
                    artifact_digest,
                    receipt_digest,
                    created_at
                FROM blogger_human_adjudications
                WHERE generation_job_id=%s
                """,
                (job_id,),
            )
            decision = cur.fetchone()

    return {
        "job_id": job["id"],
        "state": job["state"],
        "title": job["title"],
        "slug": job["slug"],
        "artifact_digest": digest_payload(artifact),
        "article_digest": artifact.get("article_digest"),
        "text_review_passed": True,
        "existing_decision": dict(decision) if decision else None,
    }


def adjudicate(
    job_id: int,
    *,
    decision: str,
    reviewer: str,
    reason: str = "",
) -> dict[str, Any]:
    decision = decision.strip().upper()
    reviewer = reviewer.strip()
    reason = reason.strip()

    if decision not in {"APPROVED", "REJECTED"}:
        raise ValueError("decision must be APPROVED or REJECTED")

    if not reviewer:
        raise ValueError("reviewer is required")

    ensure_adjudication_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            job = _load_job(cur, job_id)

            if not job:
                raise ValueError(f"generation job {job_id} does not exist")

            if job["state"] != "quality_hold":
                raise ValueError(
                    f"job {job_id} is {job['state']}, expected quality_hold"
                )

            artifact = _extract_review_artifact(job)
            artifact_digest = digest_payload(artifact)

            cur.execute(
                """
                SELECT id, decision, artifact_digest, receipt_digest
                FROM blogger_human_adjudications
                WHERE generation_job_id=%s
                """,
                (job_id,),
            )
            existing = cur.fetchone()

            if existing:
                raise ValueError(
                    f"job {job_id} already has human adjudication "
                    f"{existing['decision']}"
                )

            receipt = {
                "schema": ADJUDICATION_SCHEMA,
                "generation_job_id": job_id,
                "artifact_digest": artifact_digest,
                "article_digest": artifact["article_digest"],
                "decision": decision,
                "reviewer": reviewer,
                "reason": reason,
                "created_at": utc_now(),
            }

            receipt["receipt_digest"] = receipt_digest(receipt)

            cur.execute(
                """
                INSERT INTO blogger_human_adjudications(
                    generation_job_id,
                    artifact_digest,
                    decision,
                    reviewer,
                    reason,
                    receipt_digest,
                    receipt
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    job_id,
                    artifact_digest,
                    decision,
                    reviewer,
                    reason,
                    receipt["receipt_digest"],
                    json.dumps(receipt, ensure_ascii=False),
                ),
            )

            if decision == "APPROVED":
                cur.execute(
                    """
                    UPDATE generation_queue
                    SET
                        state='staged',
                        last_error=NULL,
                        claimed_at=NULL,
                        staged_at=NOW(),
                        updated_at=NOW()
                    WHERE id=%s
                      AND state='quality_hold'
                      AND quality->'atomic_review'->>'artifact_digest'=%s
                    RETURNING id, state, staged_at
                    """,
                    (job_id, artifact_digest),
                )
                staged = cur.fetchone()

                if not staged:
                    raise ValueError(
                        "approval receipt created but artifact-bound staging failed"
                    )

                result = {
                    "status": "STAGED",
                    "job_id": job_id,
                    "artifact_digest": artifact_digest,
                    "receipt_digest": receipt["receipt_digest"],
                    "reviewer": reviewer,
                }
            else:
                cur.execute(
                    """
                    UPDATE generation_queue
                    SET
                        last_error=%s,
                        claimed_at=NULL,
                        updated_at=NOW()
                    WHERE id=%s
                      AND state='quality_hold'
                    """,
                    (
                        reason or "human adjudication rejected",
                        job_id,
                    ),
                )

                result = {
                    "status": "REJECTED",
                    "job_id": job_id,
                    "artifact_digest": artifact_digest,
                    "receipt_digest": receipt["receipt_digest"],
                    "reviewer": reviewer,
                }

    return result

