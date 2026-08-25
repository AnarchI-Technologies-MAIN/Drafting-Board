#!/usr/bin/env python3
"""
SERVICES / SCRAPER / DISSECTOR.PY
Pillar 1: Data Ingestion & Diagram Dissection Engine (Python / Local-First)

Designed for low-memory footprint (4GB RAM envelope on Intel N150).
Extracts developer pain-point text, isolates visual schema diagrams (Mermaid.js),
hashes diagrams with SHA-256, deduplicates diagram storage, and exports semantic
JSON payloads with explicit linked_diagram_hash.
"""

import os
import sys
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DIAGRAMS_DIR = BASE_DIR / "data" / "diagrams"
PAYLOADS_DIR = BASE_DIR / "data" / "raw_payloads"
CONFIG_DIR = BASE_DIR / "data" / "config"

# Ensure target directories exist
DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)
PAYLOADS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def canonicalize_diagram(diagram_str: str) -> str:
    """Normalize line endings and whitespace for deterministic SHA-256 hashing."""
    lines = [line.rstrip() for line in diagram_str.strip().splitlines() if line.strip()]
    return "\n".join(lines)


def hash_diagram_content(canonical_str: str) -> str:
    """Compute SHA-256 hash of visual schema text."""
    return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()


def process_diagram_deduplication(diagram_code: str, diagram_format: str = "mermaid") -> dict:
    """
    Saves visual schema exactly once to local storage using SHA-256 as unique object ID.
    Returns metadata containing diagram hash, file path, and whether it was newly written.
    """
    canonical_text = canonicalize_diagram(diagram_code)
    diagram_hash = hash_diagram_content(canonical_text)
    file_name = f"{diagram_hash}.mmd"
    file_path = DIAGRAMS_DIR / file_name

    stored_newly = False
    if not file_path.exists():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(canonical_text)
        stored_newly = True

    return {
        "hash": diagram_hash,
        "format": diagram_format,
        "file_path": str(file_path.relative_to(BASE_DIR)),
        "stored_newly": stored_newly,
        "content": canonical_text
    }


def dissect_stream_item(raw_item: dict, dead_topics: list) -> dict:
    """
    Processes a single raw issue data snapshot.
    Cleans messy code blocks, extracts embedded Mermaid diagrams, checks dead_topics blacklist,
    and returns a semantic text payload metadata object.
    """
    title = raw_item.get("title", "Untitled Developer Case Study")
    raw_body = raw_item.get("raw_body", "")
    tech_stack = raw_item.get("tech_stack", [])
    item_id = raw_item.get("id", f"issue_{int(datetime.now().timestamp())}")

    # Check if any tech stack or topic is in dead_topics blacklist
    topic_cluster = raw_item.get("topic_cluster", "").lower()
    for dead in dead_topics:
        if dead.lower() in topic_cluster or any(dead.lower() in t.lower() for t in tech_stack):
            print(f"[DISSECTOR] Skipping blacklisted dead topic: '{topic_cluster}' / {tech_stack}")
            return None

    # Diagram Extraction Pattern: ```mermaid ... ``` or ```plantuml ... ```
    diagram_pattern = re.compile(r"```(mermaid|plantuml|dot)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
    
    extracted_diagram = None
    diagram_hash = None
    diagram_format = None

    match = diagram_pattern.search(raw_body)
    if match:
        diagram_format = match.group(1).lower()
        diagram_code = match.group(2)
        extracted_diagram = process_diagram_deduplication(diagram_code, diagram_format)
        diagram_hash = extracted_diagram["hash"]

        # Strip diagram block from content to separate semantic body from visual structure
        cleaned_body = diagram_pattern.sub("<!-- DIAGRAM_REFERENCE_PLACEHOLDER -->", raw_body)
    else:
        cleaned_body = raw_body

    # Clean text payload (remove excessive blank lines / clean headers)
    cleaned_body = re.sub(r"\n{3,}", "\n\n", cleaned_body).strip()
    
    # Extract summary (first non-empty paragraph)
    paragraphs = [p.strip() for p in cleaned_body.split("\n\n") if p.strip() and not p.startswith("#")]
    cleaned_summary = paragraphs[0] if paragraphs else title

    # Generate URL slug
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")

    payload = {
        "id": item_id,
        "title": title,
        "slug": slug,
        "tech_stack": tech_stack,
        "topic_cluster": raw_item.get("topic_cluster", "general-debugging"),
        "cleaned_summary": cleaned_summary,
        "cleaned_content": cleaned_body,
        "linked_diagram_hash": diagram_hash,
        "diagram_format": diagram_format,
        "source": raw_item.get("source", "github-issues-stream"),
        "extracted_at": datetime.now().isoformat()
    }

    # Export semantic payload JSON to data/raw_payloads
    payload_file = PAYLOADS_DIR / f"{payload['id']}.json"
    with open(payload_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"[DISSECTOR] Processed: {title} | Diagram Hash: {diagram_hash or 'None'} | Stored Payload: {payload_file.name}")
    return payload


def load_dead_topics() -> list:
    """Read engine configuration to obtain permanently dropped dead topics."""
    config_file = CONFIG_DIR / "engine_config.json"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("dead_topics", [])
        except Exception as e:
            print(f"[DISSECTOR] Notice: Could not read engine_config.json: {e}")
    return []


def process_file_stream(file_path: Path):
    """Memory-efficient stream reader for input raw JSON lines or list."""
    dead_topics = load_dead_topics()
    processed_count = 0

    if not file_path.exists():
        print(f"[DISSECTOR] Error: Input file {file_path} does not exist.")
        return processed_count

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            items = data if isinstance(data, list) else [data]
            for item in items:
                res = dissect_stream_item(item, dead_topics)
                if res:
                    processed_count += 1
        except json.JSONDecodeError:
            # Fallback to JSON-Lines streaming for massive raw logs
            f.seek(0)
            for line in f:
                line = line.strip()
                if line:
                    item = json.loads(line)
                    res = dissect_stream_item(item, dead_topics)
                    if res:
                        processed_count += 1

    print(f"[DISSECTOR] Stream ingestion complete. Successfully processed {processed_count} payload(s).")
    return processed_count


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Anarchi-Tech Data Ingestion & Diagram Dissector")
    parser.add_argument("--input", type=str, default=str(BASE_DIR / "data" / "raw_issues.json"), help="Path to raw issue stream JSON")
    args = parser.parse_args()

    input_path = Path(args.input)
    process_file_stream(input_path)
