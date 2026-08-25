#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime
from pathlib import Path

from db import ensure_schema, write_bot_run, write_document

ROOT = Path('/app')
DATA = ROOT / 'data'
WORKER_DIR = DATA / 'workers' / 'crawler'
WORKER_DIR.mkdir(parents=True, exist_ok=True)
RAW_PAYLOADS = DATA / 'raw_payloads'
BOT_NAME = os.getenv('BOT_NAME', 'crawler-bot')


def iter_payload_files():
    if not RAW_PAYLOADS.exists():
        return []
    return sorted(p for p in RAW_PAYLOADS.iterdir() if p.is_file() and p.suffix.lower() in {'.json', '.txt'})


def main():
    ensure_schema()
    poll_seconds = int(os.getenv('BOT_INTERVAL_SECONDS', '300'))

    while True:
        try:
            seen = 0
            payload = {'bot': BOT_NAME, 'kind': 'crawl_snapshot', 'ts': datetime.utcnow().isoformat() + 'Z', 'documents': []}

            for path in iter_payload_files():
                try:
                    raw = json.loads(path.read_text(encoding='utf-8'))
                except Exception:
                    continue

                if isinstance(raw, dict):
                    doc = raw.get('document') or raw
                    title = doc.get('title') or path.stem
                    summary = doc.get('summary') or doc.get('description') or ''
                    url = doc.get('url') or ''
                    keywords = doc.get('keywords') or []
                    image_refs = doc.get('images') or []
                    affiliate_links = doc.get('affiliate_links') or []
                    metadata = {k: v for k, v in doc.items() if k not in {'title', 'summary', 'description', 'url', 'keywords', 'images', 'affiliate_links'}}

                    write_document(
                        source_name=path.stem,
                        title=title,
                        url=url,
                        summary=summary,
                        keywords=keywords,
                        image_refs=image_refs,
                        affiliate_links=affiliate_links,
                        metadata=metadata,
                    )
                    seen += 1
                    payload['documents'].append({'path': str(path), 'title': title, 'summary': summary})

            out = WORKER_DIR / f"crawler_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
            out.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            write_bot_run(BOT_NAME, 'crawl_snapshot', payload, status='ok')
            print(f"[crawler-bot] ingested {seen} crawl documents into PostgreSQL")
        except Exception as exc:
            print(f"[crawler-bot] error: {exc}")
        time.sleep(poll_seconds)


if __name__ == '__main__':
    main()
