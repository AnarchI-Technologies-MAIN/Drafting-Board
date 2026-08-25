#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime
from pathlib import Path

from db import ensure_schema, write_bot_run

ROOT = Path('/app')
DATA = ROOT / 'data'
WORKER_DIR = DATA / 'workers' / 'research'
WORKER_DIR.mkdir(parents=True, exist_ok=True)
SOURCE = DATA / 'raw_issues.json'
BOT_NAME = os.getenv('BOT_NAME', 'research-bot')


def load_issues():
    if not SOURCE.exists():
        return []

    try:
        raw = json.loads(SOURCE.read_text(encoding='utf-8'))
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            return [raw]
    except Exception:
        return []
    return []


def main():
    ensure_schema()
    poll_seconds = int(os.getenv('BOT_INTERVAL_SECONDS', '300'))

    while True:
        try:
            issues = load_issues()
            topic_clusters = []
            keyword_set = set()

            for item in issues:
                if not isinstance(item, dict):
                    continue
                cluster = item.get('topic_cluster') or item.get('cluster') or item.get('category')
                if cluster:
                    topic_clusters.append(str(cluster))
                for keyword in item.get('keywords', []) or []:
                    value = str(keyword).strip().lower()
                    if value:
                        keyword_set.add(value)

            payload = {
                'bot': BOT_NAME,
                'kind': 'research_snapshot',
                'ts': datetime.utcnow().isoformat() + 'Z',
                'topic_clusters': sorted(set(topic_clusters)),
                'keywords': sorted(keyword_set),
                'raw_issue_count': len(issues),
                'source_file': str(SOURCE),
            }

            out = WORKER_DIR / f"research_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
            out.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            write_bot_run(BOT_NAME, 'research_snapshot', payload, status='ok')
            print(f"[research-bot] stored {len(payload['keywords'])} SEO keywords and {payload['raw_issue_count']} issue records in PostgreSQL")
        except Exception as exc:
            print(f"[research-bot] error: {exc}")
        time.sleep(poll_seconds)


if __name__ == '__main__':
    main()
