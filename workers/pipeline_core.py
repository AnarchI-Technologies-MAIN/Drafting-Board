"""Shared deterministic helpers for research, crawl, editorial QA, and files."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


USER_AGENT = os.getenv(
    "CRAWLER_USER_AGENT",
    "AnarchiEditorialResearch/1.0 (+https://www.anarchi-tech.com/blog/about)",
)
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))

PROBLEM_TERMS = {
    "error", "failed", "failure", "bug", "debug", "incident", "outage", "latency",
    "memory leak", "security", "vulnerability", "slow", "timeout", "deadlock", "race condition",
    "cost", "migration", "scaling", "production", "reliability", "performance", "optimization",
}
COMMERCIAL_TERMS = {
    "enterprise", "platform", "managed", "monitoring", "observability", "security audit",
    "cloud", "hosting", "compliance", "ci/cd", "gpu", "inference", "database", "cost optimization",
    "incident response", "developer tools", "api gateway", "kubernetes",
}
SEARCH_STOPWORDS = {
    "a", "an", "and", "at", "for", "from", "how", "in", "into", "of", "on", "or", "the", "to", "with",
    "high", "guide", "checklist", "patterns", "engineering", "implementation", "production",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as handle:
        handle.write(value)
        temporary = Path(handle.name)
    temporary.replace(path)


def request_json(url: str, *, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(
        url,
        params=params,
        timeout=HTTP_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    response.raise_for_status()
    return response.json()


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 2)


def signal_score(metric: float, ceiling: float) -> float:
    if metric <= 0:
        return 0.0
    return clamp(100.0 * math.log1p(metric) / math.log1p(ceiling))


def term_density_score(text: str, terms: set[str], base: float = 20.0, per_hit: float = 13.0) -> float:
    lowered = text.lower()
    hits = sum(1 for term in terms if term in lowered)
    return clamp(base + hits * per_hit)


def slugify(value: str, limit: int = 78) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (value[:limit].rstrip("-") or "untitled")


def keywords_from_text(text: str, vocabulary: list[str], limit: int = 18) -> list[str]:
    lowered = text.lower()
    found = [term for term in vocabulary if term.lower() in lowered]
    return list(dict.fromkeys(found))[:limit]


def hashtags_from_keywords(keywords: list[str], limit: int = 12) -> list[str]:
    tags: list[str] = []
    for keyword in keywords:
        clean = "".join(part.capitalize() for part in re.findall(r"[A-Za-z0-9]+", keyword))
        if 2 <= len(clean) <= 28:
            tags.append("#" + clean)
    return list(dict.fromkeys(tags))[:limit]


def topic_relevance(text: str, query: str, keywords: list[str]) -> dict[str, Any]:
    """Conservative lexical gate used before evidence can reach the writer.

    A single ambiguous token (for example SMART vs. smart contract) cannot pass.
    Multiword topic phrases and multiple independent query terms carry the weight.
    """
    lowered = re.sub(r"\s+", " ", (text or "").lower())
    text_tokens = set(re.findall(r"[a-z0-9+#.]{3,}", lowered))
    query_tokens = {
        token for token in re.findall(r"[a-z0-9+#.]{3,}", query.lower()) if token not in SEARCH_STOPWORDS
    }
    query_matches = sorted(query_tokens & text_tokens)
    phrases = [str(value).strip().lower() for value in keywords if " " in str(value).strip()]
    phrase_matches = sorted({phrase for phrase in phrases if phrase and phrase in lowered})
    keyword_matches = sorted(
        {
            str(value).strip().lower()
            for value in keywords
            if str(value).strip()
            and (
                str(value).strip().lower() in lowered
                if " " in str(value).strip()
                else str(value).strip().lower() in text_tokens
            )
        }
    )
    score = min(100, 13 * len(query_matches) + 27 * len(phrase_matches) + 7 * len(keyword_matches))
    passed = score >= 38 and (bool(phrase_matches) or len(query_matches) >= 2)
    return {
        "passed": passed,
        "score": score,
        "query_matches": query_matches[:12],
        "phrase_matches": phrase_matches[:8],
        "keyword_matches": keyword_matches[:12],
    }


def safe_url(value: str) -> str:
    try:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        return value
    except Exception:
        return ""


def trim_text(value: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", value or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rsplit(" ", 1)[0] + "…"


def run_forever(name: str, interval_seconds: int, callback) -> None:
    once = os.getenv("RUN_ONCE", "0").lower() in {"1", "true", "yes"}
    import time

    while True:
        started = datetime.now(timezone.utc)
        try:
            callback()
        except Exception as exc:
            print(f"[{name}] fatal cycle error: {type(exc).__name__}: {exc}", flush=True)
        if once:
            return
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        time.sleep(max(1, interval_seconds - int(elapsed)))
