#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime
from pathlib import Path

from db import ensure_schema, write_bot_run, write_document

ROOT = Path('/app')
DATA = ROOT / 'data'
WORKER_DIR = DATA / 'workers' / 'outreach'
WORKER_DIR.mkdir(parents=True, exist_ok=True)
AFFILIATES = DATA / 'affiliates.json'
BOT_NAME = os.getenv('BOT_NAME', 'outreach-bot')


def load_offers():
    if not AFFILIATES.exists():
        return []

    try:
        payload = json.loads(AFFILIATES.read_text(encoding='utf-8'))
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get('offers', [])
    except Exception:
        return []
    return []


def main():
    ensure_schema()
    poll_seconds = int(os.getenv('BOT_INTERVAL_SECONDS', '300'))

    while True:
        try:
            offers = load_offers()
            payload = {
                'bot': BOT_NAME,
                'kind': 'outreach_snapshot',
                'ts': datetime.utcnow().isoformat() + 'Z',
                'count': len(offers),
                'offers': offers,
            }

            for item in offers:
                if not isinstance(item, dict):
                    continue
                write_document(
                    source_name='affiliate-outreach',
                    title=item.get('name') or item.get('title') or 'affiliate-offer',
                    url=item.get('url') or item.get('link') or '',
                    summary=item.get('summary') or item.get('description') or '',
                    keywords=item.get('keywords') or [],
                    image_refs=item.get('images') or [],
                    affiliate_links=[item.get('url') or item.get('link') or ''],
                    metadata={
                        'campaign': item.get('campaign') or 'general',
                        'category': item.get('category') or 'affiliate',
                    },
                )

            out = WORKER_DIR / f"outreach_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
            out.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            write_bot_run(BOT_NAME, 'outreach_snapshot', payload, status='ok')
            print(f"[outreach-bot] synced {len(offers)} affiliate offers into PostgreSQL")
        except Exception as exc:
            print(f"[outreach-bot] error: {exc}")
        time.sleep(poll_seconds)


if __name__ == '__main__':
    main()
