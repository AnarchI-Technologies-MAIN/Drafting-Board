#!/usr/bin/env python3
"""Rate-limited publication, artifact freeze, and market-data handoff."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from psycopg2.extras import Json, RealDictCursor

from db import ensure_schema, get_connection, sha256_json, write_bot_run
from pipeline_core import atomic_json, atomic_text, sha256_text, utc_now, run_forever


ROOT = Path("/app")
DATA = ROOT / "data"
POSTS_DIR = DATA / "posts"
ARTIFACT_DIR = DATA / "artifacts"
MARKET_DIR = DATA / "market_bucket"
BOT_NAME = os.getenv("BOT_NAME", "publisher-bot")


def parse_slots() -> tuple[ZoneInfo, list[tuple[str, time]]]:
    zone = ZoneInfo(os.getenv("PUBLISH_TIMEZONE", "America/Chicago"))
    values = [value.strip() for value in os.getenv("PUBLISH_SLOTS", "08:15,13:15,18:15").split(",") if value.strip()]
    parsed = []
    for value in values:
        hour, minute = (int(part) for part in value.split(":", 1))
        parsed.append((value, time(hour, minute)))
    parsed.sort(key=lambda item: item[1])
    return zone, parsed


def due_slots(conn) -> tuple[datetime, list[str]]:
    zone, slots = parse_slots()
    now = datetime.now(zone)
    daily_limit = min(3, max(1, int(os.getenv("DAILY_PUBLISH_LIMIT", "3"))))
    with conn.cursor() as cur:
        cur.execute("SELECT slot_name FROM publication_slots WHERE publication_day=%s", (now.date(),))
        used = {row[0] for row in cur.fetchall()}
    available = [name for name, slot_time in slots if slot_time <= now.time() and name not in used]
    return now, available[: max(0, daily_limit - len(used))]


def frontmatter(job: dict[str, Any], artifact_id: str, published_at: str) -> str:
    seo = job.get("seo") or {}
    tags = seo.get("hashtags") or []
    metadata = {
        "title": job["title"],
        "slug": job["slug"],
        "date": published_at,
        "excerpt": job.get("summary") or "",
        "tags": tags,
        "topic_cluster": seo.get("topic_cluster") or "engineering",
        "primary_query": seo.get("primary_query") or "",
        "artifact_id": artifact_id,
        "status": "published",
    }
    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def make_market_packet(job: dict[str, Any], artifact_id: str, content_hash: str, published_at: str) -> dict[str, Any]:
    bundle = job["source_bundle"]
    packet_types: dict[str, list[Any]] = {}
    for packet in bundle.get("packets", []):
        packet_types.setdefault(packet["packet_type"], []).append(packet["payload"])
    seo = job.get("seo") or {}
    return {
        "schema": "anarchi.blog-market-data.v1",
        "authority_state": "FROZEN_PUBLISHED_ARTIFACT",
        "artifact": {
            "artifact_id": artifact_id,
            "content_hash": content_hash,
            "title": job["title"],
            "slug": job["slug"],
            "summary": job.get("summary"),
            "published_at": published_at,
            "topic_cluster": seo.get("topic_cluster"),
            "primary_query": seo.get("primary_query"),
            "hashtags": seo.get("hashtags", []),
            "source_urls": seo.get("source_urls", []),
        },
        "market_context": {
            "affiliate_opportunities": packet_types.get("affiliate_opportunity", []),
            "ad_campaign_candidates": packet_types.get("ad_campaign_candidate", []),
            "search_intake": packet_types.get("search_intake", []),
        },
        "graphic_materializer_brief": {
            "objective": "Create source-faithful blog feature and campaign graphics without granting publication authority.",
            "title": job["title"],
            "topic_cluster": seo.get("topic_cluster"),
            "key_terms": seo.get("hashtags", []),
            "reference_images": seo.get("image_references", []),
            "truth_constraints": [
                "do not invent measured performance, customer outcomes, or product capabilities",
                "source image references with unknown licenses are inspiration/provenance only",
                "published article text and artifact identity are immutable",
            ],
            "publication_authority": "NONE",
        },
        "emitted_at": published_at,
    }


def rebuild_artifact_index(conn) -> None:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT artifact_id,slug,title,summary,content_hash,metadata,frozen_at,published_at FROM artifacts ORDER BY published_at,id"
        )
        artifacts = [dict(row) for row in cur.fetchall()]
    payload = {
        "schema": "anarchi.artifact-index.v1",
        "generated_at": utc_now(),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    atomic_json(ARTIFACT_DIR / "index.json", payload)


def publish_one(slot_name: str, publication_day) -> dict[str, Any] | None:
    published_at = utc_now()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM generation_queue WHERE state='staged' ORDER BY staged_at,created_at FOR UPDATE SKIP LOCKED LIMIT 1"
            )
            job = cur.fetchone()
            if not job:
                return None
            job = dict(job)
            content_hash = sha256_text(job["body"])
            artifact_id = "artifact_" + content_hash.split(":", 1)[1][:24]
            markdown = frontmatter(job, artifact_id, published_at) + job["body"].strip() + "\n"
            post_path = POSTS_DIR / f"{job['slug']}.md"
            atomic_text(post_path, markdown)
            market_packet = make_market_packet(job, artifact_id, content_hash, published_at)
            packet_hash = sha256_json(market_packet)
            cur.execute(
                """INSERT INTO artifacts(artifact_id,generation_job_id,slug,title,summary,body,content_hash,metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    artifact_id, job["id"], job["slug"], job["title"], job.get("summary"), job["body"],
                    content_hash, Json({"seo": job.get("seo", {}), "quality": job.get("quality", {}), "model_lineage": job.get("model_lineage", {})}),
                ),
            )
            cur.execute(
                "INSERT INTO market_data_bucket(artifact_id,packet_hash,payload) VALUES (%s,%s,%s)",
                (artifact_id, packet_hash, Json(market_packet)),
            )
            cur.execute(
                "INSERT INTO publication_slots(publication_day,slot_name,generation_job_id) VALUES (%s,%s,%s)",
                (publication_day, slot_name, job["id"]),
            )
            cur.execute(
                "UPDATE generation_queue SET state='published',published_at=NOW(),updated_at=NOW() WHERE id=%s",
                (job["id"],),
            )
            cur.execute(
                """INSERT INTO generated_posts(slug,title,topic,summary,body,status,metadata)
                   VALUES (%s,%s,%s,%s,%s,'published',%s)
                   ON CONFLICT(slug) DO NOTHING""",
                (job["slug"], job["title"], (job.get("seo") or {}).get("topic_cluster"), job.get("summary"), job["body"], Json({"artifact_id": artifact_id})),
            )
        atomic_json(MARKET_DIR / f"{artifact_id}.json", market_packet)
        rebuild_artifact_index(conn)
    try:
        post_path.chmod(0o444)
    except OSError:
        pass
    return {"artifact_id": artifact_id, "job_id": job["id"], "slug": job["slug"], "slot": slot_name}


def cycle() -> None:
    with get_connection() as conn:
        now, slots = due_slots(conn)
    published = []
    for slot in slots:
        result = publish_one(slot, now.date())
        if not result:
            break
        published.append(result)
    payload = {
        "schema": "anarchi.publication-cycle.v1",
        "captured_at": utc_now(),
        "timezone": str(now.tzinfo),
        "due_slots": slots,
        "published": published,
        "daily_limit": min(3, max(1, int(os.getenv("DAILY_PUBLISH_LIMIT", "3")))),
    }
    write_bot_run(BOT_NAME, "publication_cycle", payload)
    print(f"[{BOT_NAME}] published {len(published)} staged posts; {len(slots)} slots were due", flush=True)


def main() -> None:
    ensure_schema()
    run_forever(BOT_NAME, int(os.getenv("BOT_INTERVAL_SECONDS", "300")), cycle)


if __name__ == "__main__":
    main()
