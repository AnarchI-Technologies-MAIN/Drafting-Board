#!/usr/bin/env python3
"""Multi-source enrichment worker for active search-intake packets."""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from db import append_packet, claim_intakes, ensure_schema, set_intake_state, write_bot_run
from pipeline_core import (
    HTTP_TIMEOUT,
    USER_AGENT,
    atomic_json,
    hashtags_from_keywords,
    safe_url,
    sha256_text,
    trim_text,
    topic_relevance,
    utc_now,
    run_forever,
)


ROOT = Path("/app")
DATA = ROOT / "data"
AUDIT_DIR = DATA / "crawl_audits"
BOT_NAME = os.getenv("BOT_NAME", "crawler-bot")
MAX_RESULTS_PER_SOURCE = int(os.getenv("MAX_RESULTS_PER_SOURCE", "6"))
MAX_PAGE_FETCHES = int(os.getenv("MAX_PAGE_FETCHES", "10"))
MAX_EXCERPT_CHARS = int(os.getenv("MAX_SOURCE_EXCERPT_CHARS", "12000"))
AUTHORITATIVE_DOMAINS = {
    "local-moe-inference": ["ollama.com", "docs.ollama.com", "docs.vllm.ai"],
    "cloud-native-reliability": ["kubernetes.io", "opentelemetry.io", "ebpf.io", "isovalent.com"],
    "software-supply-chain": ["slsa.dev", "cisa.gov", "docs.sigstore.dev", "owasp.org"],
    "database-performance": ["postgresql.org", "pgbouncer.org"],
    "node-platform-failures": ["nodejs.org", "typescriptlang.org"],
    "wallet-contract-security": ["soliditylang.org", "docs.soliditylang.org", "ethereum.org", "eips.ethereum.org"],
}
PRIMARY_SOURCE_SEEDS = {
    "local-moe-inference": [
        ("Ollama context length", "https://docs.ollama.com/context-length"),
        ("Ollama FAQ", "https://docs.ollama.com/faq"),
        ("vLLM optimization and tuning", "https://docs.vllm.ai/en/latest/configuration/optimization.html"),
    ],
    "cloud-native-reliability": [
        ("Kubernetes observability", "https://kubernetes.io/docs/concepts/cluster-administration/observability/"),
        ("Kubernetes application troubleshooting", "https://kubernetes.io/docs/tasks/debug/debug-application/"),
        ("Kubernetes pod resource management", "https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/"),
        ("OpenTelemetry metrics", "https://opentelemetry.io/docs/concepts/signals/metrics/"),
    ],
    "software-supply-chain": [
        ("SLSA specification", "https://slsa.dev/spec/v1.2/"),
        ("CISA software bill of materials", "https://www.cisa.gov/sbom"),
        ("Sigstore documentation", "https://docs.sigstore.dev/"),
        ("OWASP component verification standard", "https://owasp.org/www-project-software-component-verification-standard/"),
    ],
    "database-performance": [
        ("PostgreSQL monitoring database activity", "https://www.postgresql.org/docs/current/monitoring.html"),
        ("PostgreSQL viewing locks", "https://www.postgresql.org/docs/current/monitoring-locks.html"),
        ("PostgreSQL concurrency control", "https://www.postgresql.org/docs/current/mvcc.html"),
        ("PostgreSQL explicit locking", "https://www.postgresql.org/docs/current/explicit-locking.html"),
        ("PostgreSQL locking and indexes", "https://www.postgresql.org/docs/current/locking-indexes.html"),
    ],
    "node-platform-failures": [
        ("Node.js diagnostic reports", "https://nodejs.org/api/report.html"),
        ("Node.js performance measurement APIs", "https://nodejs.org/api/perf_hooks.html"),
        ("Node.js memory diagnostics", "https://nodejs.org/en/learn/diagnostics/memory/understanding-and-tuning-memory"),
        ("Node.js command-line diagnostics", "https://nodejs.org/api/cli.html"),
    ],
    "wallet-contract-security": [
        ("Solidity security considerations", "https://docs.soliditylang.org/en/latest/security-considerations.html"),
        ("Solidity SMTChecker formal verification", "https://docs.soliditylang.org/en/latest/smtchecker.html"),
        ("Ethereum typed structured data signing", "https://eips.ethereum.org/EIPS/eip-712"),
        ("Contract signature validation", "https://eips.ethereum.org/EIPS/eip-1271"),
        ("Ethereum smart contract security", "https://ethereum.org/en/developers/docs/smart-contracts/security/"),
    ],
}


def search_duckduckgo(query: str) -> list[dict[str, Any]]:
    response = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for node in soup.select(".result"):
        link = node.select_one(".result__a")
        snippet = node.select_one(".result__snippet")
        if not link:
            continue
        url = link.get("href", "")
        if "duckduckgo.com/l/?" in url:
            url = unquote(parse_qs(urlparse(url).query).get("uddg", [url])[0])
        results.append(
            {
                "provider": "duckduckgo-html",
                "title": link.get_text(" ", strip=True),
                "url": safe_url(url),
                "snippet": snippet.get_text(" ", strip=True) if snippet else "",
                "metrics": {"rank": len(results) + 1},
            }
        )
        if len(results) >= MAX_RESULTS_PER_SOURCE:
            break
    return results


def search_stack_overflow(query: str) -> list[dict[str, Any]]:
    response = requests.get(
        "https://api.stackexchange.com/2.3/search/advanced",
        params={"site": "stackoverflow", "q": query, "pagesize": MAX_RESULTS_PER_SOURCE, "sort": "votes", "order": "desc"},
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    results = []
    for item in response.json().get("items", []):
        results.append(
            {
                "provider": "stackoverflow-api",
                "title": html.unescape(item.get("title", "")),
                "url": safe_url(item.get("link", "")),
                "snippet": "Tags: " + ", ".join(item.get("tags", [])),
                "metrics": {
                    "views": item.get("view_count", 0),
                    "score": item.get("score", 0),
                    "answers": item.get("answer_count", 0),
                    "accepted_answer": item.get("is_answered", False),
                },
            }
        )
    return results


def search_bing_rss(query: str) -> list[dict[str, Any]]:
    response = requests.get(
        "https://www.bing.com/search",
        params={"q": query, "format": "rss"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml,application/xml"},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    results = []
    for item in root.findall(".//item"):
        results.append(
            {
                "provider": "bing-rss",
                "title": html.unescape(item.findtext("title", default="")),
                "url": safe_url(item.findtext("link", default="")),
                "snippet": trim_text(BeautifulSoup(item.findtext("description", default=""), "html.parser").get_text(" ", strip=True), 1200),
                "metrics": {"rank": len(results) + 1},
            }
        )
        if len(results) >= MAX_RESULTS_PER_SOURCE:
            break
    return results


def search_github(query: str) -> list[dict[str, Any]]:
    response = requests.get(
        "https://api.github.com/search/issues",
        params={"q": f"{query} is:issue", "sort": "comments", "order": "desc", "per_page": MAX_RESULTS_PER_SOURCE},
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    results = []
    for item in response.json().get("items", []):
        results.append(
            {
                "provider": "github-issues-api",
                "title": item.get("title", ""),
                "url": safe_url(item.get("html_url", "")),
                "snippet": trim_text(item.get("body") or "", 1000),
                "metrics": {
                    "comments": item.get("comments", 0),
                    "state": item.get("state"),
                    "labels": [label.get("name", "") for label in item.get("labels", [])],
                    "updated_at": item.get("updated_at"),
                },
            }
        )
    return results


def search_hacker_news(query: str) -> list[dict[str, Any]]:
    response = requests.get(
        "https://hn.algolia.com/api/v1/search",
        params={"query": query, "tags": "story", "hitsPerPage": MAX_RESULTS_PER_SOURCE},
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    results = []
    for item in response.json().get("hits", []):
        url = item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID')}"
        results.append(
            {
                "provider": "hacker-news-algolia",
                "title": item.get("title", ""),
                "url": safe_url(url),
                "snippet": "",
                "metrics": {"points": item.get("points", 0), "comments": item.get("num_comments", 0)},
            }
        )
    return results


def allowed_by_robots(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
        return parser.can_fetch(USER_AGENT, url)
    except Exception:
        return False


def extract_page(url: str) -> dict[str, Any] | None:
    if not url or not allowed_by_robots(url):
        return None
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type or len(response.content) > 4_000_000:
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    for node in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        node.decompose()
    title = trim_text((soup.title.get_text(" ", strip=True) if soup.title else ""), 300)
    description_node = soup.select_one('meta[name="description"]')
    description = trim_text(description_node.get("content", "") if description_node else "", 600)
    main = soup.select_one("#docContent, article, main, .documentation, .docs-content") or soup.body or soup
    excerpt = trim_text(main.get_text(" ", strip=True), MAX_EXCERPT_CHARS)
    images = []
    for node in soup.select('meta[property="og:image"], meta[name="twitter:image"], img[src]'):
        source = node.get("content") or node.get("src") or ""
        if source.startswith("//"):
            source = "https:" + source
        if source.startswith("http"):
            images.append(
                {
                    "url": source,
                    "alt": trim_text(node.get("alt", ""), 250),
                    "source_page": url,
                    "license_status": "unknown-reference-only",
                }
            )
        if len(images) >= 6:
            break
    return {
        "title": title,
        "description": description,
        "excerpt": excerpt,
        "excerpt_hash": sha256_text(excerpt),
        "images": images,
        "canonical_url": response.url,
        "retrieved_at": utc_now(),
        "copyright_handling": "bounded research excerpt with provenance; not a republishing grant",
    }


def enrich_intake(intake: dict[str, Any]) -> dict[str, Any]:
    query = intake["query"]
    secondary = (intake.get("seo_plan") or {}).get("secondary_keywords", [])
    discovery_query = " ".join(str(value) for value in secondary[:4]) or " ".join(query.split()[:6])
    broad_discovery_query = " ".join(str(value) for value in secondary[:2]) or " ".join(query.split()[:3])
    results: list[dict[str, Any]] = []
    errors = []
    authority_domains = AUTHORITATIVE_DOMAINS.get(intake.get("topic_cluster"), [])
    for name, connector in (
        ("duckduckgo-html", search_duckduckgo),
        ("bing-rss", search_bing_rss),
        ("stackoverflow-api", search_stack_overflow),
        ("github-issues-api", search_github),
        ("hacker-news-algolia", search_hacker_news),
    ):
        try:
            if name in {"duckduckgo-html", "bing-rss", "stackoverflow-api"}:
                connector_query = query
            else:
                connector_query = broad_discovery_query
            results.extend(connector(connector_query))
        except Exception as exc:
            errors.append({"provider": name, "error": f"{type(exc).__name__}: {exc}"[:500]})
    for domain in authority_domains[:3]:
        try:
            for result in search_bing_rss(f"site:{domain} {query}"):
                result["provider"] = "bing-rss-authority"
                results.append(result)
        except Exception as exc:
            errors.append({"provider": "bing-rss-authority", "domain": domain, "error": f"{type(exc).__name__}: {exc}"[:500]})
    for title, url in PRIMARY_SOURCE_SEEDS.get(intake.get("topic_cluster"), []):
        results.append(
            {
                "provider": "curated-primary-source",
                "title": title,
                "url": url,
                "snippet": f"First-party documentation selected for the {intake.get('topic_cluster')} evidence layer.",
                "metrics": {"authority": "first-party", "selection": "versioned editorial policy"},
            }
        )
    unique: dict[str, dict[str, Any]] = {}
    for result in results:
        if result.get("url") and result["url"] not in unique:
            unique[result["url"]] = result
    documents = []
    rejected = []
    image_count = 0
    vocabulary = list(dict.fromkeys((intake.get("seo_plan") or {}).get("keyword_family", []) + query.lower().split()))
    def ranking_score(item: dict[str, Any]) -> int:
        relevance_score = topic_relevance(
            " ".join([item.get("title", ""), item.get("snippet", "")]), query, vocabulary
        )["score"]
        return relevance_score + (1000 if item.get("provider") == "curated-primary-source" else 0)

    ranked_results = sorted(unique.values(), key=ranking_score, reverse=True)
    for index, result in enumerate(ranked_results):
        page = None
        if index < MAX_PAGE_FETCHES or result.get("provider") == "curated-primary-source":
            try:
                page = extract_page(result["url"])
            except Exception as exc:
                errors.append({"provider": "page-fetch", "url": result["url"], "error": f"{type(exc).__name__}: {exc}"[:300]})
        text = " ".join([result.get("title", ""), result.get("snippet", ""), (page or {}).get("excerpt", "")])
        surface_relevance = topic_relevance(
            " ".join([result.get("title", ""), result.get("snippet", "")]), query, vocabulary
        )
        relevance = topic_relevance(text, query, vocabulary)
        hostname = urlparse(result["url"]).netloc.lower().removeprefix("www.")
        authoritative = any(hostname == domain or hostname.endswith("." + domain) for domain in authority_domains)
        relevance["surface"] = surface_relevance
        relevance["authoritative_domain"] = authoritative
        relevance["policy_version"] = 2
        relevance["passed"] = bool(relevance["passed"] and (surface_relevance["passed"] or authoritative))
        if not relevance["passed"]:
            rejected.append(
                {"provider": result["provider"], "url": result["url"], "title": result.get("title"), "relevance": relevance}
            )
            continue
        matched_keywords = [keyword for keyword in vocabulary if keyword.lower() in text.lower()][:18]
        doc = {
            "schema": "anarchi.source-document.v1",
            "query": query,
            "provider": result["provider"],
            "title": result.get("title") or (page or {}).get("title", ""),
            "url": result["url"],
            "search_snippet": trim_text(result.get("snippet", ""), 1200),
            "metrics": result.get("metrics", {}),
            "page": page,
            "keywords": matched_keywords,
            "relevance": relevance,
            "captured_at": utc_now(),
        }
        packet_id, inserted = append_packet(intake["id"], "source_document", BOT_NAME, doc)
        if inserted:
            documents.append({"packet_id": packet_id, "provider": result["provider"], "url": result["url"], "title": doc["title"]})
        for image in (page or {}).get("images", []):
            _, image_inserted = append_packet(intake["id"], "source_image_reference", BOT_NAME, image)
            image_count += int(image_inserted)
    keyword_family = (intake.get("seo_plan") or {}).get("keyword_family", [])
    tags = hashtags_from_keywords(keyword_family)
    append_packet(
        intake["id"],
        "seo_enrichment",
        BOT_NAME,
        {
            "schema": "anarchi.seo-enrichment.v1",
            "primary_query": query,
            "keyword_family": keyword_family,
            "hashtags": tags,
            "title_guidance": "descriptive, concise, distinct, and aligned to the actual problem solved",
            "image_guidance": "use only licensed or original relevant images with descriptive filenames and alt text",
            "structured_data_type": "BlogPosting",
            "captured_at": utc_now(),
        },
    )
    providers = sorted({document["provider"] for document in documents})
    manifest = {
        "schema": "anarchi.crawl-manifest.v1",
        "query": query,
        "discovery_query": discovery_query,
        "broad_discovery_query": broad_discovery_query,
        "providers_attempted": ["duckduckgo-html", "bing-rss", "stackoverflow-api", "github-issues-api", "hacker-news-algolia"],
        "providers_with_results": providers,
        "raw_unique_result_count": len(unique),
        "unique_result_count": len(documents),
        "rejected_off_topic_count": len(rejected),
        "rejected_off_topic_sample": rejected[:12],
        "new_document_packets": len(documents),
        "new_image_packets": image_count,
        "errors": errors,
        "completed_at": utc_now(),
    }
    append_packet(intake["id"], "crawl_manifest", BOT_NAME, manifest)
    return manifest


def cycle() -> None:
    batch = claim_intakes("queued", "crawling", int(os.getenv("CRAWL_BATCH_SIZE", "3")))
    summaries = []
    for intake in batch:
        try:
            manifest = enrich_intake(intake)
            minimum = int(os.getenv("MIN_SOURCE_RESULTS", "4"))
            if manifest["unique_result_count"] >= minimum:
                set_intake_state(intake["id"], "enriched")
            elif int(intake.get("attempts", 0)) >= 3:
                set_intake_state(intake["id"], "held", f"only {manifest['unique_result_count']} source results")
            else:
                set_intake_state(intake["id"], "queued", f"only {manifest['unique_result_count']} source results; retrying")
            summaries.append({"intake_id": intake["id"], **manifest})
        except Exception as exc:
            state = "held" if int(intake.get("attempts", 0)) >= 3 else "queued"
            set_intake_state(intake["id"], state, f"{type(exc).__name__}: {exc}")
            summaries.append({"intake_id": intake["id"], "error": f"{type(exc).__name__}: {exc}"})
    audit = {"schema": "anarchi.crawl-cycle.v1", "captured_at": utc_now(), "intakes": summaries}
    if batch:
        filename = datetime.now(timezone.utc).strftime("crawl_audit_%Y%m%dT%H%M%SZ.json")
        atomic_json(AUDIT_DIR / filename, audit)
    write_bot_run(BOT_NAME, "crawl_cycle", audit)
    print(f"[{BOT_NAME}] processed {len(batch)} intake queries", flush=True)


def main() -> None:
    ensure_schema()
    run_forever(BOT_NAME, int(os.getenv("BOT_INTERVAL_SECONDS", "900")), cycle)


if __name__ == "__main__":
    main()
