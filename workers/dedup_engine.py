#!/usr/bin/env python3
import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from db import ensure_schema, get_connection, write_bot_run

ROOT = Path('/app')
DATA = ROOT / 'data'
WORKER_DIR = DATA / 'workers' / 'dedup'
WORKER_DIR.mkdir(parents=True, exist_ok=True)
BOT_NAME = os.getenv('BOT_NAME', 'dedup-engine')


def normalize_content(text):
    """Normalize text for deduplication: lowercase, remove punctuation, collapse whitespace."""
    if not isinstance(text, str):
        text = str(text)
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text.strip())
    return text


def compute_hash(text):
    """MD5 hash of normalized content."""
    normalized = normalize_content(text)
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def semantic_similarity(hash1, hash2):
    """
    Simple similarity metric: compare normalized strings.
    For now, exact hash match = 100%, no match = 0%.
    (Future: use embeddings for fuzzy matching)
    """
    return 100.0 if hash1 == hash2 else 0.0


def check_duplicate(content, conn):
    """
    Check if content is a duplicate.
    Returns: (is_duplicate, duplicate_id, similarity_score)
    """
    content_hash = compute_hash(content)
    
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, similarity_score FROM content_hashes WHERE content_hash = %s LIMIT 1",
            (content_hash,),
        )
        row = cur.fetchone()
        if row:
            return True, row[0], 100.0
        
        cur.execute("INSERT INTO content_hashes (content_hash, normalized_content) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING id", (content_hash, normalize_content(content)))
        result = cur.fetchone()
        if result:
            return False, None, 0.0
    
    return False, None, 0.0


def process_crawl_documents(conn):
    """
    Find raw crawl_documents that may be duplicates of each other.
    Mark duplicates and return stats.
    """
    stats = {
        'checked': 0,
        'duplicates_found': 0,
        'marked_for_dedup': 0,
    }
    
    with conn.cursor() as cur:
        cur.execute("SELECT id, title, summary, url FROM crawl_documents WHERE metadata->>'dedup_status' IS NULL ORDER BY created_at ASC")
        rows = cur.fetchall()
    
    for doc_id, title, summary, url in rows:
        stats['checked'] += 1
        content = f"{title or ''} {summary or ''}"
        
        is_dup, dup_id, sim_score = check_duplicate(content, conn)
        
        if is_dup and dup_id != doc_id:
            stats['duplicates_found'] += 1
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE crawl_documents SET metadata = jsonb_set(metadata, '{dedup_status}', '\"duplicate\"'::jsonb) WHERE id = %s",
                    (doc_id,),
                )
            stats['marked_for_dedup'] += 1
        else:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE crawl_documents SET metadata = jsonb_set(metadata, '{dedup_status}', '\"unique\"'::jsonb) WHERE id = %s",
                    (doc_id,),
                )
    
    return stats


def get_dedup_summary(conn):
    """Get summary of dedup status."""
    with conn.cursor() as cur:
        cur.execute("SELECT metadata->>'dedup_status', COUNT(*) FROM crawl_documents GROUP BY metadata->>'dedup_status'")
        rows = cur.fetchall()
    
    return {status: count for status, count in rows if status}


def main():
    ensure_schema()
    poll_seconds = int(os.getenv('BOT_INTERVAL_SECONDS', '600'))
    
    while True:
        try:
            with get_connection() as conn:
                stats = process_crawl_documents(conn)
                summary = get_dedup_summary(conn)
                conn.commit()
            
            payload = {
                'bot': BOT_NAME,
                'kind': 'dedup_snapshot',
                'ts': datetime.utcnow().isoformat() + 'Z',
                'checked': stats['checked'],
                'duplicates_found': stats['duplicates_found'],
                'marked_for_dedup': stats['marked_for_dedup'],
                'summary': summary,
            }
            
            out = WORKER_DIR / f"dedup_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
            out.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            write_bot_run(BOT_NAME, 'dedup_snapshot', payload, status='ok')
            print(f"[dedup-engine] checked {stats['checked']} docs, found {stats['duplicates_found']} duplicates, marked {stats['marked_for_dedup']} for filtering")
            print(f"               dedup status summary: {summary}")
        except Exception as exc:
            print(f"[dedup-engine] error: {exc}")
        
        time.sleep(poll_seconds)


if __name__ == '__main__':
    main()
