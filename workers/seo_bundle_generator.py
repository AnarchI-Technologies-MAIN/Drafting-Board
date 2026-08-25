#!/usr/bin/env python3
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from db import ensure_schema, get_connection, write_bot_run

ROOT = Path('/app')
DATA = ROOT / 'data'
WORKER_DIR = DATA / 'workers' / 'seo_bundle'
WORKER_DIR.mkdir(parents=True, exist_ok=True)
BOT_NAME = os.getenv('BOT_NAME', 'seo-bundle-gen')


def extract_primary_keyword(title, keywords):
    """Extract primary keyword from title or keyword list."""
    if keywords and len(keywords) > 0:
        return keywords[0]
    words = re.findall(r'\b[a-z]+(?:[_-][a-z]+)*\b', title.lower())
    return ' '.join(words[:2]) if words else 'technical-article'


def generate_long_tail_keywords(primary, title, keywords):
    """Generate long-tail keyword variations from primary + title."""
    long_tail = []
    title_words = title.lower().split()
    
    combinations = [
        f"{primary} guide",
        f"{primary} tutorial",
        f"{primary} best practices",
        f"{primary} troubleshooting",
        f"how to {primary}",
        f"{primary} for beginners",
    ]
    
    for combo in combinations:
        if len(combo) < 60:
            long_tail.append(combo)
    
    for kw in keywords[:3]:
        long_tail.append(f"{primary} {kw}")
    
    return list(set(long_tail))[:10]


def generate_hashtags(primary, keywords):
    """Generate hashtags from primary keyword and keywords list."""
    hashtags = []
    
    hashtags.append(f"#{primary.replace(' ', '')}")
    hashtags.append(f"#{primary.replace(' ', '').title()}")
    
    for kw in keywords[:5]:
        hashtag = f"#{kw.replace(' ', '').replace('-', '').replace('_', '')}"
        if len(hashtag) < 30:
            hashtags.append(hashtag)
    
    generic_tags = ["#DevOps", "#SoftwareDevelopment", "#TechWriting", "#Deterministic", "#Verification"]
    hashtags.extend(generic_tags)
    
    return list(set(hashtags))[:15]


def generate_meta_description(title, summary):
    """Generate meta description (< 160 chars)."""
    if summary and len(summary) > 30:
        desc = summary[:155]
        if not desc.endswith('.'):
            desc = desc.rsplit(' ', 1)[0] + '.'
    else:
        desc = title
    
    return desc[:160]


def generate_json_ld_schema(title, summary, url, keywords):
    """Generate JSON-LD Article schema for SEO."""
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title[:110],
        "description": summary[:160] if summary else title,
        "url": url,
        "author": {
            "@type": "Organization",
            "name": "Anarchi-Technologies",
            "url": "https://www.anarchi-tech.com",
        },
        "publisher": {
            "@type": "Organization",
            "name": "Anarchi-Technologies",
            "logo": {
                "@type": "ImageObject",
                "url": "https://www.anarchi-tech.com/assets/anarchi-emblem.png",
            },
        },
        "datePublished": datetime.utcnow().isoformat() + "Z",
        "keywords": ", ".join(keywords[:10]),
    }
    return schema


def process_crawl_documents(conn):
    """Generate SEO bundles for documents without one."""
    stats = {
        'processed': 0,
        'bundles_created': 0,
    }
    
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, summary, url, keywords
            FROM crawl_documents
            WHERE id NOT IN (SELECT DISTINCT crawl_document_id FROM seo_bundles)
            AND metadata->>'dedup_status' != 'duplicate'
            ORDER BY created_at DESC
            LIMIT 50
            """
        )
        rows = cur.fetchall()
    
    for doc_id, title, summary, url, keywords_json in rows:
        stats['processed'] += 1
        
        try:
            keywords = json.loads(keywords_json) if keywords_json else []
            if not isinstance(keywords, list):
                keywords = []
        except Exception:
            keywords = []
        
        primary = extract_primary_keyword(title or '', keywords)
        long_tail = generate_long_tail_keywords(primary, title or '', keywords)
        hashtags = generate_hashtags(primary, keywords)
        meta_desc = generate_meta_description(title or '', summary or '')
        schema = generate_json_ld_schema(title or '', summary or '', url or '', keywords)
        
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO seo_bundles (crawl_document_id, primary_keyword, long_tail_keywords, hashtags, meta_description, schema_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    doc_id,
                    primary,
                    json.dumps(long_tail),
                    json.dumps(hashtags),
                    meta_desc,
                    json.dumps(schema),
                ),
            )
            stats['bundles_created'] += 1
    
    return stats


def get_bundle_summary(conn):
    """Get summary of SEO bundles created."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM seo_bundles")
        total = cur.fetchone()[0]
    
    return {'total_bundles': total}


def main():
    ensure_schema()
    poll_seconds = int(os.getenv('BOT_INTERVAL_SECONDS', '600'))
    
    while True:
        try:
            with get_connection() as conn:
                stats = process_crawl_documents(conn)
                summary = get_bundle_summary(conn)
                conn.commit()
            
            payload = {
                'bot': BOT_NAME,
                'kind': 'seo_bundle_snapshot',
                'ts': datetime.utcnow().isoformat() + 'Z',
                'processed': stats['processed'],
                'bundles_created': stats['bundles_created'],
                'summary': summary,
            }
            
            out = WORKER_DIR / f"seo_bundle_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
            out.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            write_bot_run(BOT_NAME, 'seo_bundle_snapshot', payload, status='ok')
            print(f"[seo-bundle-gen] processed {stats['processed']} docs, created {stats['bundles_created']} bundles")
            print(f"                  total bundles in db: {summary['total_bundles']}")
        except Exception as exc:
            print(f"[seo-bundle-gen] error: {exc}")
        
        time.sleep(poll_seconds)


if __name__ == '__main__':
    main()
