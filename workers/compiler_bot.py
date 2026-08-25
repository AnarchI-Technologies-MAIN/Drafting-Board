#!/usr/bin/env python3
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from db import ensure_schema, write_bot_run, write_post

ROOT = Path('/app')
DATA = ROOT / 'data'
WORKER_DIR = DATA / 'workers' / 'compiler'
WORKER_DIR.mkdir(parents=True, exist_ok=True)
POSTS_DIR = DATA / 'posts'
POSTS_DIR.mkdir(parents=True, exist_ok=True)
RAW_PAYLOADS = DATA / 'raw_payloads'
BOT_NAME = os.getenv('BOT_NAME', 'compiler-bot')


def slugify(value):
    text = re.sub(r'[^a-z0-9\s-]', '', value.lower())
    text = re.sub(r'\s+', '-', text.strip())
    return text[:80].strip('-') or 'untitled-post'


def read_json_file(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def main():
    ensure_schema()
    poll_seconds = int(os.getenv('BOT_INTERVAL_SECONDS', '300'))

    while True:
        try:
            payload = {'bot': BOT_NAME, 'kind': 'compiler_snapshot', 'ts': datetime.utcnow().isoformat() + 'Z', 'posts': []}

            files = sorted(RAW_PAYLOADS.iterdir()) if RAW_PAYLOADS.exists() else []
            for item in files:
                if item.suffix.lower() != '.json':
                    continue
                doc = read_json_file(item)
                if not isinstance(doc, dict):
                    continue

                title = doc.get('title') or doc.get('name') or item.stem.replace('-', ' ').title()
                topic = doc.get('topic_cluster') or doc.get('category') or 'engineering'
                summary = doc.get('summary') or doc.get('description') or 'SEO-driven engineering analysis and systems research.'
                slug = slugify(title)

                body = f"# {title}\n\n{summary}\n\n## Context\n\n{json.dumps(doc, indent=2, ensure_ascii=False)}\n"
                frontmatter = (
                    "---\n"
                    f"title: \"{title}\"\n"
                    f"topic_cluster: \"{topic}\"\n"
                    f"summary: \"{summary}\"\n"
                    "date: " + datetime.utcnow().strftime('%Y-%m-%d') + "\n"
                    "---\n\n"
                )
                post_path = POSTS_DIR / f"{slug}.md"
                post_path.write_text(frontmatter + body, encoding='utf-8')
                write_post(slug, title, topic, body, status='draft', metadata={'source_file': str(item), 'summary': summary})
                payload['posts'].append({'slug': slug, 'title': title, 'topic': topic, 'path': str(post_path)})

            out = WORKER_DIR / f"compiler_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
            out.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            write_bot_run(BOT_NAME, 'compiler_snapshot', payload, status='ok')
            print(f"[compiler-bot] generated {len(payload['posts'])} draft posts for the blog")
        except Exception as exc:
            print(f"[compiler-bot] error: {exc}")
        time.sleep(poll_seconds)


if __name__ == '__main__':
    main()
