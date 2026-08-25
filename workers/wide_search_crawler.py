#!/usr/bin/env python3
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

from db import ensure_schema, write_bot_run, write_document

ROOT = Path('/app')
DATA = ROOT / 'data'
WORKER_DIR = DATA / 'workers' / 'crawler_wide'
WORKER_DIR.mkdir(parents=True, exist_ok=True)
RAW_PAYLOADS = DATA / 'raw_payloads'
RAW_PAYLOADS.mkdir(parents=True, exist_ok=True)
BOT_NAME = os.getenv('BOT_NAME', 'wide-search-crawler')

DEFAULT_SEARCH_TERMS = [
    "cloud server deployment WSL",
    "WSL2 integration best practices",
    "code debugging error handling",
    "distributed systems determinism",
    "nodejs performance optimization",
    "solidity smart contract security",
    "web3 wallet security bug fixes",
    "serverless architecture patterns",
    "typescript strict mode debugging",
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def search_duckduckgo(query, max_results=5):
    """Scrape DuckDuckGo search results (free, no API key)."""
    if not requests:
        return []
    
    results = []
    try:
        url = "https://duckduckgo.com/html/"
        params = {"q": query}
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        for item in soup.find_all('div', class_='result'):
            if len(results) >= max_results:
                break
            
            title_elem = item.find('a', class_='result__a')
            snippet_elem = item.find('a', class_='result__snippet')
            
            if title_elem and snippet_elem:
                title = title_elem.get_text(strip=True)
                snippet = snippet_elem.get_text(strip=True)
                url = title_elem.get('href', '')
                
                results.append({
                    'source': 'duckduckgo',
                    'title': title,
                    'snippet': snippet,
                    'url': url,
                    'rank': len(results) + 1,
                })
    except Exception as exc:
        print(f"[wide-search-crawler] DuckDuckGo error: {exc}")
    
    return results


def search_github_issues(topic, max_results=5):
    """Fetch GitHub issues related to topic."""
    if not requests:
        return []
    
    results = []
    try:
        query = f"{topic} is:issue is:open label:bug"
        url = "https://api.github.com/search/issues"
        params = {"q": query, "sort": "stars", "order": "desc", "per_page": max_results}
        headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github.v3+json"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        for item in response.json().get('items', []):
            results.append({
                'source': 'github-issues',
                'title': item.get('title', ''),
                'snippet': item.get('body', '')[:500],
                'url': item.get('html_url', ''),
                'rank': len(results) + 1,
                'metadata': {
                    'stars': item.get('stargazers_count', 0),
                    'comments': item.get('comments', 0),
                    'labels': [l['name'] for l in item.get('labels', [])],
                },
            })
    except Exception as exc:
        print(f"[wide-search-crawler] GitHub API error: {exc}")
    
    return results


def extract_keywords_from_text(text):
    """Simple keyword extraction: extract noun phrases, tech terms."""
    words = re.findall(r'\b[a-z]+(?:[_-][a-z]+)*\b', text.lower())
    tech_terms = {'node', 'python', 'javascript', 'typescript', 'wsl', 'docker', 'kubernetes',
                  'cloud', 'database', 'api', 'rest', 'graphql', 'solidity', 'ethereum', 'web3',
                  'serverless', 'lambda', 'aws', 'azure', 'gcp', 'git', 'github', 'error',
                  'debugging', 'performance', 'optimization', 'security', 'encryption',
                  'distributed', 'consensus', 'blockchain', 'contract', 'deterministic'}
    return list(set(w for w in words if w in tech_terms))


def process_search_result(result):
    """Convert search result to structured document."""
    title = result.get('title', 'Untitled')
    snippet = result.get('snippet', '')
    url = result.get('url', '')
    source = result.get('source', 'unknown')
    
    keywords = extract_keywords_from_text(f"{title} {snippet}")
    
    return {
        'title': title,
        'url': url,
        'summary': snippet,
        'keywords': keywords,
        'images': [],  # TODO: extract images from URL later
        'affiliate_links': [],
        'metadata': {
            'source': source,
            'rank': result.get('rank', 0),
            'traffic_estimate': max(1000, 5000 - (result.get('rank', 1) * 500)),
            'extra_metadata': result.get('metadata', {}),
        },
    }


def main():
    ensure_schema()
    poll_seconds = int(os.getenv('BOT_INTERVAL_SECONDS', '1800'))  # 30 min default
    
    while True:
        try:
            search_terms = os.getenv('SEARCH_TERMS', ','.join(DEFAULT_SEARCH_TERMS)).split(',')
            search_terms = [t.strip() for t in search_terms if t.strip()]
            
            all_results = []
            payload = {
                'bot': BOT_NAME,
                'kind': 'wide_search_snapshot',
                'ts': datetime.utcnow().isoformat() + 'Z',
                'search_terms': search_terms,
                'documents': [],
            }
            
            for term in search_terms:
                print(f"[wide-search-crawler] searching: {term}")
                
                duckduckgo_results = search_duckduckgo(term, max_results=5)
                github_results = search_github_issues(term, max_results=3)
                
                for result in duckduckgo_results + github_results:
                    doc = process_search_result(result)
                    all_results.append(doc)
                    
                    write_document(
                        source_name=result.get('source', 'web-search'),
                        title=doc['title'],
                        url=doc['url'],
                        summary=doc['summary'],
                        keywords=doc['keywords'],
                        image_refs=doc['images'],
                        affiliate_links=doc['affiliate_links'],
                        metadata=doc['metadata'],
                    )
                    payload['documents'].append({
                        'title': doc['title'],
                        'url': doc['url'],
                        'rank': result.get('rank', 0),
                    })
            
            out = WORKER_DIR / f"wide_search_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
            out.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            write_bot_run(BOT_NAME, 'wide_search_snapshot', payload, status='ok')
            print(f"[wide-search-crawler] ingested {len(all_results)} documents from {len(search_terms)} search terms")
        except Exception as exc:
            print(f"[wide-search-crawler] error: {exc}")
        
        time.sleep(poll_seconds)


if __name__ == '__main__':
    main()
