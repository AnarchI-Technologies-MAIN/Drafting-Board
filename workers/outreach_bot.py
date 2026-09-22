#!/usr/bin/env python3
"""Non-consuming monetization observer for enriched editorial packets."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from db import (
    append_packet,
    claim_intakes,
    ensure_schema,
    get_packets,
    set_intake_state,
    update_observer_offset,
    write_bot_run,
)
from pipeline_core import HTTP_TIMEOUT, USER_AGENT, safe_url, trim_text, utc_now, run_forever


ROOT = Path("/app")
DATA = ROOT / "data"
AFFILIATES = DATA / "affiliates.json"
ADS = DATA / "ads_config.json"
BOT_NAME = os.getenv("BOT_NAME", "outreach-bot")


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def searchable_text(packets: list[dict[str, Any]]) -> str:
    values = []
    for packet in packets:
        if packet["packet_type"] in {"source_document", "search_intake", "seo_enrichment"}:
            values.append(json.dumps(packet["payload"], ensure_ascii=False, default=str))
    return " ".join(values).lower()


def discover_program_evidence(product_name: str) -> list[dict[str, str]]:
    query = f'"{product_name}" affiliate partner program enterprise'
    response = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for item in soup.select(".result")[:4]:
        link = item.select_one(".result__a")
        snippet = item.select_one(".result__snippet")
        if not link:
            continue
        url = safe_url(link.get("href", ""))
        if not url:
            continue
        results.append(
            {
                "title": trim_text(link.get_text(" ", strip=True), 250),
                "url": url,
                "snippet": trim_text(snippet.get_text(" ", strip=True) if snippet else "", 700),
            }
        )
    return results


def score_offer(offer: dict[str, Any], corpus: str) -> tuple[int, list[str]]:
    matched = [keyword for keyword in offer.get("keywords", []) if str(keyword).lower() in corpus]
    relevance = min(100, len(matched) * 18 + (15 if offer.get("category", "") in corpus else 0))
    score = round(0.62 * relevance + 0.38 * float(offer.get("payout_score", 0)))
    return score, matched


def observe_intake(intake: dict[str, Any]) -> dict[str, Any]:
    packets = get_packets(intake["id"], active_only=True)
    corpus = searchable_text(packets)
    offers = load_json(AFFILIATES, [])
    ads = load_json(ADS, {}).get("providers", [])
    opportunity_count = 0
    verified_count = 0
    discovery_errors = []
    ranked = []
    for offer in offers:
        score, matched = score_offer(offer, corpus)
        if score < int(os.getenv("MIN_AFFILIATE_OPPORTUNITY_SCORE", "48")):
            continue
        ranked.append((score, matched, offer))
    ranked.sort(key=lambda item: item[0], reverse=True)
    for score, matched, offer in ranked[:4]:
        evidence = []
        try:
            evidence = discover_program_evidence(offer.get("name", ""))
        except Exception as exc:
            discovery_errors.append({"offer": offer.get("id"), "error": f"{type(exc).__name__}: {exc}"[:400]})
        verified = bool(offer.get("affiliate_verified", False))
        payload = {
            "schema": "anarchi.affiliate-opportunity.v1",
            "offer_id": offer.get("id"),
            "name": offer.get("name"),
            "category": offer.get("category"),
            "destination_url": offer.get("url") if verified else None,
            "catalog_url": offer.get("url"),
            "cta_text": offer.get("cta_text"),
            "description": offer.get("description"),
            "relevance_score": score,
            "payout_proxy_score": offer.get("payout_score", 0),
            "matched_keywords": matched,
            "verification_status": "verified" if verified else "candidate-needs-contract-verification",
            "discovery_evidence": evidence,
            "placement_rule": "disclose material relationship and place only when it directly helps the reader",
            "observed_at": utc_now(),
        }
        append_packet(intake["id"], "affiliate_opportunity", BOT_NAME, payload)
        opportunity_count += 1
        verified_count += int(verified)
    campaign_count = 0
    commercial_score = float(intake.get("value_score") or 0)
    for provider in ads:
        payload = {
            "schema": "anarchi.ad-campaign-candidate.v1",
            "campaign_id": f"{provider.get('id')}-{intake['topic_cluster']}",
            "provider_id": provider.get("id"),
            "provider_name": provider.get("name"),
            "topic_cluster": intake["topic_cluster"],
            "query": intake["query"],
            "search_intent": intake["search_intent"],
            "commercial_intent_score": commercial_score,
            "volume_class": "high-proxy" if float(intake.get("traffic_score") or 0) >= 75 else "qualified-niche-proxy",
            "measurement_status": "modeled-not-measured",
            "placement": provider.get("slot"),
            "creative": {key: provider.get(key) for key in ("badge", "headline", "description", "cta_text")},
            "target_url": provider.get("target_url"),
            "safety": "contextual placement only; never disguise advertising as editorial evidence",
            "observed_at": utc_now(),
        }
        append_packet(intake["id"], "ad_campaign_candidate", BOT_NAME, payload)
        campaign_count += 1
    manifest = {
        "schema": "anarchi.monetization-manifest.v1",
        "affiliate_candidates": opportunity_count,
        "verified_affiliate_candidates": verified_count,
        "ad_campaign_candidates": campaign_count,
        "discovery_errors": discovery_errors,
        "policy": "unverified offers may inform research but cannot be published as affiliate links",
        "completed_at": utc_now(),
    }
    append_packet(intake["id"], "monetization_manifest", BOT_NAME, manifest)
    update_observer_offset(BOT_NAME, intake["id"], [packet["id"] for packet in packets])
    return manifest


def cycle() -> None:
    batch = claim_intakes("enriched", "monetizing", int(os.getenv("MONETIZATION_BATCH_SIZE", "6")))
    results = []
    for intake in batch:
        try:
            manifest = observe_intake(intake)
            set_intake_state(intake["id"], "ready")
            results.append({"intake_id": intake["id"], **manifest})
        except Exception as exc:
            next_state = "held" if int(intake.get("attempts", 0)) >= 4 else "enriched"
            set_intake_state(intake["id"], next_state, f"{type(exc).__name__}: {exc}")
            results.append({"intake_id": intake["id"], "error": f"{type(exc).__name__}: {exc}"})
    payload = {"schema": "anarchi.monetization-cycle.v1", "captured_at": utc_now(), "intakes": results}
    write_bot_run(BOT_NAME, "monetization_cycle", payload)
    print(f"[{BOT_NAME}] observed {len(batch)} enriched intakes without consuming their packets", flush=True)


def main() -> None:
    ensure_schema()
    run_forever(BOT_NAME, int(os.getenv("BOT_INTERVAL_SECONDS", "900")), cycle)


if __name__ == "__main__":
    main()
