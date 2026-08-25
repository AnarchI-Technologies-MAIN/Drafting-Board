#!/usr/bin/env python3
import json
import os
import time
import re
import yaml
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

try:
    import requests
except ImportError:
    requests = None

from db import ensure_schema, get_connection, write_bot_run

ROOT = Path('/app')
DATA = ROOT / 'data'
WORKER_DIR = DATA / 'workers' / 'llm_blogger'
POSTS_DIR = DATA / 'posts'
WORKER_DIR.mkdir(parents=True, exist_ok=True)
POSTS_DIR.mkdir(parents=True, exist_ok=True)
BOT_NAME = os.getenv('BOT_NAME', 'llm-blogger')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://ollama:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'mistral')


def get_unwritten_topics(conn):
    """Get topics with dedup'd docs and SEO bundles but no blog post yet."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                cd.id,
                cd.title,
                cd.summary,
                cd.url,
                cd.keywords,
                sb.primary_keyword,
                sb.long_tail_keywords,
                sb.hashtags,
                sb.meta_description,
                sb.schema_json
            FROM crawl_documents cd
            JOIN seo_bundles sb ON sb.crawl_document_id = cd.id
            WHERE cd.metadata->>'dedup_status' != 'duplicate'
            AND NOT EXISTS (
                SELECT 1 FROM generated_posts gp 
                WHERE (gp.metadata->>'source_doc_id')::int = cd.id
            )
            ORDER BY cd.created_at DESC
            LIMIT 3
            """
        )
        rows = cur.fetchall()
    
    return rows


def build_prompt(doc_id, title, summary, keywords, primary_kw, long_tail, meta_desc, hashtags):
    """Build prompt for LLM blogger."""
    keywords_str = ', '.join(json.loads(keywords) if isinstance(keywords, str) else keywords or [])
    long_tail_str = ', '.join(json.loads(long_tail) if isinstance(long_tail, str) else long_tail or [])
    hashtags_str = ', '.join(json.loads(hashtags) if isinstance(hashtags, str) else hashtags or [])
    
    prompt = f"""You are a technical blog writer for Anarchi-Technologies.

TOPIC: {title}
DESCRIPTION: {summary or 'A technical topic in software development, systems, and determinism.'}

PRIMARY KEYWORD: {primary_kw}
LONG-TAIL KEYWORDS: {long_tail_str}
META DESCRIPTION: {meta_desc}
HASHTAGS: {hashtags_str}

VOICE & STYLE:
- Confident, authoritative, deterministic
- Skeptical of hype, grounded in first principles
- Technical depth with practical examples
- Clear, direct language
- Problem-solution oriented

REQUIREMENTS:
1. Write a comprehensive blog post (800-1200 words)
2. Start with an engaging hook
3. Include practical code examples where relevant
4. Add a "Why This Matters" section
5. End with actionable takeaways
6. Naturally incorporate the primary and long-tail keywords
7. Avoid plagiarism - synthesize, rewrite, add original insights
8. Link to authoritative sources where applicable

OUTPUT FORMAT:
Provide the response in valid YAML frontmatter + Markdown:

---
title: "Blog Post Title Here"
slug: "url-friendly-slug"
date: "{datetime.utcnow().isoformat()}Z"
excerpt: "{meta_desc}"
tags: {hashtags_str.split(', ')}
topic: "{primary_kw}"
status: published
---

# Your Blog Post Title

[Your markdown content here, with proper formatting, headings, code blocks, etc.]
"""
    return prompt


def call_ollama(prompt):
    """Call Ollama API to generate content."""
    if not requests:
        print("[llm-blogger] requests library not available")
        return None
    
    try:
        url = f"{OLLAMA_URL}/api/generate"
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.7,
            "top_p": 0.9,
        }
        
        print(f"[llm-blogger] calling Ollama at {url} with model {OLLAMA_MODEL}")
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        return result.get('response', '')
    except Exception as exc:
        print(f"[llm-blogger] Ollama API error: {exc}")
        return None


def parse_frontmatter(text):
    """Parse YAML frontmatter + markdown from LLM response."""
    if not text.strip().startswith('---'):
        return None, text
    
    parts = text.split('---', 2)
    if len(parts) < 3:
        return None, text
    
    try:
        frontmatter = yaml.safe_load(parts[1])
        content = parts[2].strip()
        return frontmatter, content
    except Exception as exc:
        print(f"[llm-blogger] YAML parse error: {exc}")
        return None, text


def sanitize_slug(text):
    """Convert title to URL-friendly slug."""
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug[:80]


def store_blog_post(conn, doc_id, title, frontmatter, content, meta_desc, hashtags_str):
    """Store generated blog post to database and filesystem."""
    slug = frontmatter.get('slug') if frontmatter else sanitize_slug(title)
    
    post_data = {
        'title': title,
        'slug': slug,
        'body': content,
        'summary': meta_desc,
        'topic': frontmatter.get('topic', '') if frontmatter else '',
        'tags': hashtags_str.split(', ') if hashtags_str else [],
        'metadata': {
            'source_doc_id': doc_id,
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'model': OLLAMA_MODEL,
            'frontmatter': frontmatter,
        },
    }
    
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO generated_posts (title, slug, body, summary, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                post_data['title'],
                post_data['slug'],
                post_data['body'],
                post_data['summary'],
                json.dumps(post_data['metadata']),
            ),
        )
        post_id = cur.fetchone()[0]
    
    post_file = POSTS_DIR / f"{slug}.md"
    post_markdown = f"""---
title: {post_data['title']}
slug: {slug}
date: {datetime.utcnow().isoformat()}Z
excerpt: {meta_desc}
tags: {json.dumps(post_data['tags'])}
status: published
---

{content}
"""
    post_file.write_text(post_markdown, encoding='utf-8')
    
    return post_id, slug


def main():
    ensure_schema()
    poll_seconds = int(os.getenv('BOT_INTERVAL_SECONDS', '1200'))  # 20 min default
    
    while True:
        try:
            with get_connection() as conn:
                topics = get_unwritten_topics(conn)
                
                if not topics:
                    print("[llm-blogger] no unwritten topics found, waiting...")
                else:
                    for row in topics:
                        doc_id, title, summary, url, keywords, primary_kw, long_tail, hashtags, meta_desc, schema = row
                        
                        print(f"[llm-blogger] generating blog post for: {title}")
                        
                        prompt = build_prompt(doc_id, title, summary, keywords, primary_kw, long_tail, meta_desc, hashtags)
                        response = call_ollama(prompt)
                        
                        if response:
                            frontmatter, content = parse_frontmatter(response)
                            post_id, slug = store_blog_post(conn, doc_id, title, frontmatter, content, meta_desc, hashtags)
                            conn.commit()
                            
                            payload = {
                                'bot': BOT_NAME,
                                'kind': 'blog_post_generated',
                                'ts': datetime.utcnow().isoformat() + 'Z',
                                'post_id': post_id,
                                'slug': slug,
                                'title': title,
                                'source_doc_id': doc_id,
                            }
                            write_bot_run(BOT_NAME, 'blog_post_generated', payload, status='ok')
                            print(f"[llm-blogger] ✓ generated post: {slug}")
                        else:
                            print(f"[llm-blogger] ✗ failed to generate content for: {title}")
        except Exception as exc:
            print(f"[llm-blogger] error: {exc}")
        
        time.sleep(poll_seconds)


if __name__ == '__main__':
    main()
