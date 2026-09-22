"""Durable PostgreSQL contracts for the editorial packet pipeline.

The packet bucket is append-only for producers and observers. The finalizer never
deletes evidence: it atomically copies active packets into a generation job and
marks those packet rows consumed. Operators see an empty active bucket while the
audit trail remains intact.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Iterable

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from blog_loop.legacy_bridge import LegacyNormalizationError
from blog_loop.serialization import (
    load_editorial_intake_policy,
    prepare_serializable_source_bundle,
)



DEFAULT_DATABASE_URL = "postgresql://anarchi:anarchi_password@postgres:5432/anarchi_db"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_connection():
    return psycopg2.connect(get_database_url())


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS bot_runs (
        id BIGSERIAL PRIMARY KEY,
        bot_name TEXT NOT NULL,
        run_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ok',
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS crawl_documents (
        id BIGSERIAL PRIMARY KEY,
        source_name TEXT NOT NULL,
        title TEXT,
        url TEXT,
        summary TEXT,
        keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
        image_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
        affiliate_links JSONB NOT NULL DEFAULT '[]'::jsonb,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS generated_posts (
        id BIGSERIAL PRIMARY KEY,
        slug TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        topic TEXT,
        summary TEXT,
        body TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS intake_queries (
        id BIGSERIAL PRIMARY KEY,
        fingerprint TEXT NOT NULL UNIQUE,
        query TEXT NOT NULL,
        topic_cluster TEXT NOT NULL,
        search_intent TEXT NOT NULL,
        tier SMALLINT NOT NULL CHECK (tier BETWEEN 1 AND 5),
        traffic_score NUMERIC(6,2) NOT NULL,
        value_score NUMERIC(6,2) NOT NULL,
        problem_score NUMERIC(6,2) NOT NULL,
        trend_score NUMERIC(6,2) NOT NULL,
        total_score NUMERIC(6,2) NOT NULL,
        evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
        seo_plan JSONB NOT NULL DEFAULT '{}'::jsonb,
        state TEXT NOT NULL DEFAULT 'queued' CHECK (
            state IN ('queued','crawling','enriched','monetizing','ready','serializing','drained','held','failed')
        ),
        attempts INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        claimed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS packet_bucket (
        id BIGSERIAL PRIMARY KEY,
        intake_id BIGINT NOT NULL REFERENCES intake_queries(id),
        packet_type TEXT NOT NULL,
        producer TEXT NOT NULL,
        packet_hash TEXT NOT NULL UNIQUE,
        payload JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        consumed_at TIMESTAMPTZ,
        consumed_by TEXT,
        generation_job_id BIGINT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS observer_offsets (
        observer_name TEXT NOT NULL,
        intake_id BIGINT NOT NULL REFERENCES intake_queries(id),
        last_packet_id BIGINT NOT NULL DEFAULT 0,
        observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (observer_name, intake_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS generation_queue (
        id BIGSERIAL PRIMARY KEY,
        intake_id BIGINT NOT NULL UNIQUE REFERENCES intake_queries(id),
        packet_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
        source_bundle JSONB NOT NULL,
        state TEXT NOT NULL DEFAULT 'queued' CHECK (
            state IN ('queued','generating','staged','quality_hold','published','failed')
        ),
        attempts INTEGER NOT NULL DEFAULT 0,
        title TEXT,
        slug TEXT UNIQUE,
        summary TEXT,
        body TEXT,
        seo JSONB NOT NULL DEFAULT '{}'::jsonb,
        quality JSONB NOT NULL DEFAULT '{}'::jsonb,
        model_lineage JSONB NOT NULL DEFAULT '{}'::jsonb,
        last_error TEXT,
        claimed_at TIMESTAMPTZ,
        staged_at TIMESTAMPTZ,
        published_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS artifacts (
        id BIGSERIAL PRIMARY KEY,
        artifact_id TEXT NOT NULL UNIQUE,
        generation_job_id BIGINT NOT NULL UNIQUE REFERENCES generation_queue(id),
        slug TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        summary TEXT,
        body TEXT NOT NULL,
        content_hash TEXT NOT NULL UNIQUE,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        frozen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        published_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_data_bucket (
        id BIGSERIAL PRIMARY KEY,
        artifact_id TEXT NOT NULL UNIQUE REFERENCES artifacts(artifact_id),
        packet_hash TEXT NOT NULL UNIQUE,
        payload JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        observed_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS publication_slots (
        publication_day DATE NOT NULL,
        slot_name TEXT NOT NULL,
        generation_job_id BIGINT NOT NULL UNIQUE REFERENCES generation_queue(id),
        published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (publication_day, slot_name)
    )
    """,
    """
    CREATE OR REPLACE FUNCTION reject_frozen_artifact_mutation() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'published artifacts are immutable';
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS artifacts_are_immutable ON artifacts",
    """
    CREATE TRIGGER artifacts_are_immutable
    BEFORE UPDATE OR DELETE ON artifacts
    FOR EACH ROW EXECUTE FUNCTION reject_frozen_artifact_mutation()
    """,
    "CREATE INDEX IF NOT EXISTS idx_bot_runs_created_at ON bot_runs(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_intake_state_score ON intake_queries(state,total_score DESC,created_at)",
    "CREATE INDEX IF NOT EXISTS idx_packet_active ON packet_bucket(intake_id,id) WHERE consumed_at IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_packet_type ON packet_bucket(packet_type,created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_generation_state ON generation_queue(state,created_at)",
    "CREATE INDEX IF NOT EXISTS idx_artifacts_published ON artifacts(published_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_market_unobserved ON market_data_bucket(id) WHERE observed_at IS NULL",
    "CREATE OR REPLACE VIEW active_packet_bucket AS SELECT * FROM packet_bucket WHERE consumed_at IS NULL",
]


def ensure_schema() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            for statement in SCHEMA_STATEMENTS:
                cur.execute(statement)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)


def sha256_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_bot_run(bot_name: str, run_type: str, payload: Any, status: str = "ok") -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO bot_runs(bot_name,run_type,payload,status) VALUES (%s,%s,%s,%s)",
                (bot_name, run_type, Json(payload), status),
            )


def upsert_intake(candidate: dict[str, Any]) -> tuple[int, bool]:
    fingerprint = candidate.get("fingerprint") or sha256_json(
        {"query": candidate["query"].strip().lower(), "cluster": candidate["topic_cluster"]}
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intake_queries(
                    fingerprint,query,topic_cluster,search_intent,tier,traffic_score,value_score,
                    problem_score,trend_score,total_score,evidence,seo_plan
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (fingerprint) DO UPDATE SET
                    evidence=EXCLUDED.evidence,seo_plan=EXCLUDED.seo_plan,
                    traffic_score=EXCLUDED.traffic_score,value_score=EXCLUDED.value_score,
                    problem_score=EXCLUDED.problem_score,trend_score=EXCLUDED.trend_score,
                    total_score=EXCLUDED.total_score,updated_at=NOW()
                RETURNING id,(xmax = 0) AS inserted
                """,
                (
                    fingerprint, candidate["query"], candidate["topic_cluster"], candidate["search_intent"],
                    candidate["tier"], candidate["traffic_score"], candidate["value_score"],
                    candidate["problem_score"], candidate["trend_score"], candidate["total_score"],
                    Json(candidate.get("evidence", [])), Json(candidate.get("seo_plan", {})),
                ),
            )
            row = cur.fetchone()
            return int(row[0]), bool(row[1])


def append_packet(intake_id: int, packet_type: str, producer: str, payload: Any) -> tuple[int, bool]:
    packet_hash = sha256_json(
        {"intake_id": intake_id, "packet_type": packet_type, "producer": producer, "payload": payload}
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO packet_bucket(intake_id,packet_type,producer,packet_hash,payload)
                   VALUES (%s,%s,%s,%s,%s) ON CONFLICT(packet_hash) DO NOTHING RETURNING id""",
                (intake_id, packet_type, producer, packet_hash, Json(payload)),
            )
            row = cur.fetchone()
            if row:
                return int(row[0]), True
            cur.execute("SELECT id FROM packet_bucket WHERE packet_hash=%s", (packet_hash,))
            return int(cur.fetchone()[0]), False


def claim_intakes(expected_state: str, claimed_state: str, limit: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                WITH candidates AS (
                    SELECT id FROM intake_queries WHERE state=%s
                    ORDER BY total_score DESC,created_at FOR UPDATE SKIP LOCKED LIMIT %s
                )
                UPDATE intake_queries iq SET state=%s,claimed_at=NOW(),attempts=attempts+1,updated_at=NOW()
                FROM candidates c WHERE iq.id=c.id RETURNING iq.*
                """,
                (expected_state, limit, claimed_state),
            )
            return [dict(row) for row in cur.fetchall()]


def set_intake_state(intake_id: int, state: str, error: str | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE intake_queries SET state=%s,last_error=%s,claimed_at=NULL,updated_at=NOW() WHERE id=%s",
                (state, error[:1000] if error else None, intake_id),
            )


def get_packets(intake_id: int, active_only: bool = True) -> list[dict[str, Any]]:
    predicate = "AND consumed_at IS NULL" if active_only else ""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT id,packet_type,producer,packet_hash,payload,created_at FROM packet_bucket WHERE intake_id=%s {predicate} ORDER BY id",
                (intake_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def update_observer_offset(observer_name: str, intake_id: int, packet_ids: Iterable[int]) -> None:
    last_packet_id = max(packet_ids, default=0)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO observer_offsets(observer_name,intake_id,last_packet_id) VALUES (%s,%s,%s)
                   ON CONFLICT(observer_name,intake_id) DO UPDATE SET
                   last_packet_id=GREATEST(observer_offsets.last_packet_id,EXCLUDED.last_packet_id),observed_at=NOW()""",
                (observer_name, intake_id, last_packet_id),
            )




def serialize_ready_intakes(limit: int, finalizer_name: str) -> list[int]:
    """Serialize only ready intakes that pass deterministic normalization.

    Failure is fail-closed:
    - no generation job is created,
    - active packets remain unconsumed,
    - the intake becomes held with an explicit normalization fracture.
    """
    created: list[int] = []
    policy = load_editorial_intake_policy()

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM intake_queries WHERE state='ready'
                   ORDER BY total_score DESC,created_at
                   FOR UPDATE SKIP LOCKED LIMIT %s""",
                (limit,),
            )

            for intake in [dict(row) for row in cur.fetchall()]:
                cur.execute(
                    """SELECT id,packet_type,producer,packet_hash,payload,created_at
                       FROM packet_bucket
                       WHERE intake_id=%s
                       AND consumed_at IS NULL
                       ORDER BY id""",
                    (intake["id"],),
                )

                packets = [
                    dict(row)
                    for row in cur.fetchall()
                ]

                if not packets:
                    cur.execute(
                        """UPDATE intake_queries
                           SET state='held',
                               last_error='ready intake had no active packets',
                               updated_at=NOW()
                           WHERE id=%s""",
                        (intake["id"],),
                    )
                    continue

                try:
                    bundle = prepare_serializable_source_bundle(
                        intake,
                        packets,
                        policy=policy,
                    )
                except Exception as exc:
                    error = (
                        "generation normalization failed: "
                        + type(exc).__name__
                        + ": "
                        + str(exc)
                    )[:1000]

                    cur.execute(
                        """UPDATE intake_queries
                           SET state='held',
                               last_error=%s,
                               claimed_at=NULL,
                               updated_at=NOW()
                           WHERE id=%s""",
                        (
                            error,
                            intake["id"],
                        ),
                    )
                    continue

                packet_ids = [
                    packet["id"]
                    for packet in packets
                ]

                cur.execute(
                    """INSERT INTO generation_queue(
                           intake_id,
                           packet_ids,
                           source_bundle
                       )
                       VALUES (%s,%s,%s)
                       ON CONFLICT(intake_id)
                       DO NOTHING
                       RETURNING id""",
                    (
                        intake["id"],
                        Json(packet_ids),
                        Json(bundle),
                    ),
                )

                row = cur.fetchone()

                if row:
                    job_id = int(row["id"])
                    created.append(job_id)
                else:
                    cur.execute(
                        """SELECT id
                           FROM generation_queue
                           WHERE intake_id=%s""",
                        (intake["id"],),
                    )
                    existing = cur.fetchone()

                    if not existing:
                        raise RuntimeError(
                            "generation queue conflict produced no durable job"
                        )

                    job_id = int(existing["id"])

                cur.execute(
                    """UPDATE packet_bucket
                       SET consumed_at=NOW(),
                           consumed_by=%s,
                           generation_job_id=%s
                       WHERE intake_id=%s
                       AND consumed_at IS NULL""",
                    (
                        finalizer_name,
                        job_id,
                        intake["id"],
                    ),
                )

                cur.execute(
                    """UPDATE intake_queries
                       SET state='drained',
                           claimed_at=NULL,
                           updated_at=NOW()
                       WHERE id=%s""",
                    (intake["id"],),
                )

    return created


def claim_generation_jobs(limit: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                WITH jobs AS (
                    SELECT id FROM generation_queue WHERE state='queued'
                    ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT %s
                )
                UPDATE generation_queue g SET state='generating',attempts=attempts+1,claimed_at=NOW(),updated_at=NOW()
                FROM jobs WHERE g.id=jobs.id RETURNING g.*
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def stage_generation_job(job_id: int, result: dict[str, Any]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE generation_queue SET state=%s,title=%s,slug=%s,summary=%s,body=%s,
                   seo=%s,quality=%s,model_lineage=%s,last_error=%s,claimed_at=NULL,
                   staged_at=CASE WHEN %s='staged' THEN NOW() ELSE staged_at END,updated_at=NOW() WHERE id=%s""",
                (
                    result["state"], result.get("title"), result.get("slug"), result.get("summary"),
                    result.get("body"), Json(result.get("seo", {})), Json(result.get("quality", {})),
                    Json(result.get("model_lineage", {})), result.get("error"), result["state"], job_id,
                ),
            )


def requeue_generation_job(job_id: int, error: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE generation_queue SET state=CASE WHEN attempts>=5 THEN 'failed' ELSE 'queued' END,
                   last_error=%s,claimed_at=NULL,updated_at=NOW() WHERE id=%s""",
                (error[:2000], job_id),
            )


# Compatibility helpers for the dashboard and explicitly enabled legacy profile.
def write_document(source_name, title, url, summary, keywords=None, image_refs=None, affiliate_links=None, metadata=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO crawl_documents(source_name,title,url,summary,keywords,image_refs,affiliate_links,metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (source_name, title, url, summary, Json(keywords or []), Json(image_refs or []), Json(affiliate_links or []), Json(metadata or {})),
            )


def write_post(slug, title, topic, body, summary=None, status="draft", metadata=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO generated_posts(slug,title,topic,summary,body,status,metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(slug) DO UPDATE SET title=EXCLUDED.title,topic=EXCLUDED.topic,
                   summary=EXCLUDED.summary,body=EXCLUDED.body,status=EXCLUDED.status,metadata=EXCLUDED.metadata""",
                (slug, title, topic, summary, body, status, Json(metadata or {})),
            )
