import json
import os

import psycopg2


DEFAULT_DATABASE_URL = "postgresql://anarchi:anarchi_password@postgres:5432/anarchi_db"


def get_database_url():
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_connection():
    return psycopg2.connect(get_database_url())


def ensure_schema():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS content_hashes (
                    id SERIAL PRIMARY KEY,
                    content_hash TEXT NOT NULL UNIQUE,
                    normalized_content TEXT,
                    source_url TEXT,
                    is_duplicate_of INT REFERENCES content_hashes(id),
                    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    similarity_score FLOAT DEFAULT 0.0
                );
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_content_hashes_created_at ON content_hashes (first_seen_at DESC);"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS seo_bundles (
                    id SERIAL PRIMARY KEY,
                    crawl_document_id INT REFERENCES crawl_documents(id),
                    primary_keyword TEXT,
                    long_tail_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
                    hashtags JSONB NOT NULL DEFAULT '[]'::jsonb,
                    meta_description TEXT,
                    schema_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_seo_bundles_document_id ON seo_bundles (crawl_document_id);"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_runs (
                    id SERIAL PRIMARY KEY,
                    bot_name TEXT NOT NULL,
                    run_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ok',
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS crawl_documents (
                    id SERIAL PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    title TEXT,
                    url TEXT,
                    summary TEXT,
                    keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
                    image_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
                    affiliate_links JSONB NOT NULL DEFAULT '[]'::jsonb,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS generated_posts (
                    id SERIAL PRIMARY KEY,
                    slug TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    topic TEXT,
                    summary TEXT,
                    body TEXT,
                    status TEXT NOT NULL DEFAULT 'draft',
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS traffic_events (
                    id SERIAL PRIMARY KEY,
                    post_slug TEXT,
                    title TEXT,
                    source TEXT,
                    impressions INTEGER NOT NULL DEFAULT 0,
                    clicks INTEGER NOT NULL DEFAULT 0,
                    conversions INTEGER NOT NULL DEFAULT 0,
                    revenue NUMERIC(12,2) NOT NULL DEFAULT 0,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS affiliate_events (
                    id SERIAL PRIMARY KEY,
                    offer_name TEXT,
                    offer_url TEXT,
                    campaign TEXT,
                    clicks INTEGER NOT NULL DEFAULT 0,
                    conversions INTEGER NOT NULL DEFAULT 0,
                    revenue NUMERIC(12,2) NOT NULL DEFAULT 0,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_bot_runs_created_at ON bot_runs (created_at DESC);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_crawl_documents_created_at ON crawl_documents (created_at DESC);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_generated_posts_created_at ON generated_posts (created_at DESC);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_traffic_events_created_at ON traffic_events (created_at DESC);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_affiliate_events_created_at ON affiliate_events (created_at DESC);"
            )


def write_bot_run(bot_name, run_type, payload, status="ok"):
    ensure_schema()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_runs (bot_name, run_type, payload, status)
                VALUES (%s, %s, %s, %s)
                """,
                (bot_name, run_type, json.dumps(payload), status),
            )
            return cur.rowcount


def write_document(source_name, title, url, summary, keywords=None, image_refs=None, affiliate_links=None, metadata=None):
    ensure_schema()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO crawl_documents (source_name, title, url, summary, keywords, image_refs, affiliate_links, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source_name,
                    title,
                    url,
                    summary,
                    json.dumps(keywords or []),
                    json.dumps(image_refs or []),
                    json.dumps(affiliate_links or []),
                    json.dumps(metadata or {}),
                ),
            )
            return cur.rowcount


def write_post(slug, title, topic, body, summary=None, status="draft", metadata=None):
    ensure_schema()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
               INSERT INTO generated_posts (slug, title, topic, summary, body, status, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    title = EXCLUDED.title,
                    topic = EXCLUDED.topic,
                   summary = EXCLUDED.summary,
                   body = EXCLUDED.body,
                   status = EXCLUDED.status,
                   metadata = EXCLUDED.metadata,
                   created_at = NOW()
               """,
               (slug, title, topic, summary, body, status, json.dumps(metadata or {})),
            )
            return cur.rowcount


def record_traffic_event(post_slug, title=None, source='unknown', impressions=0, clicks=0, conversions=0, revenue=0.0, metadata=None):
    ensure_schema()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
               """
               INSERT INTO traffic_events (post_slug, title, source, impressions, clicks, conversions, revenue, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               """,
               (
                   post_slug,
                   title,
                   source,
                   int(impressions or 0),
                   int(clicks or 0),
                   int(conversions or 0),
                   float(revenue or 0.0),
                   json.dumps(metadata or {}),
               ),
            )
            return cur.rowcount


def record_affiliate_event(offer_name, offer_url='', campaign='general', clicks=0, conversions=0, revenue=0.0, metadata=None):
    ensure_schema()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
               """
               INSERT INTO affiliate_events (offer_name, offer_url, campaign, clicks, conversions, revenue, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               """,
               (
                   offer_name,
                   offer_url,
                   campaign,
                   int(clicks or 0),
                   int(conversions or 0),
                   float(revenue or 0.0),
                   json.dumps(metadata or {}),
               ),
            )
            return cur.rowcount
