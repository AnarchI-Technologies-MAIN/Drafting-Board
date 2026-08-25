#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


def load_db_helpers():
    try:
        from db import ensure_schema, get_connection
        return ensure_schema, get_connection
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PostgreSQL support is missing. Install it with: pip install psycopg2-binary\n"
            "or from the project root: pip install -r requirements.txt"
        ) from exc
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Unable to import the shared database helpers from workers/db.py") from exc


ensure_schema = None
get_connection = None

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def human_size(num_bytes):
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    return f"{value:.2f} {units[unit_index]}" if unit_index else f"{int(value)} B"


def parse_metadata_value(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def summarize_storage():
    bucket_names = [
        "posts",
        "workers",
        "diagrams",
        "raw_payloads",
        "config",
        "screenshots",
    ]
    print("BUCKET STORAGE SUMMARY")
    print("=" * 80)
    total_bytes = 0
    table = []
    for bucket in bucket_names:
        folder = DATA_DIR / bucket
        if not folder.exists():
            table.append((bucket, 0, 0, "not present"))
            continue
        files = [p for p in folder.rglob("*") if p.is_file()]
        size = sum(p.stat().st_size for p in files)
        total_bytes += size
        table.append((bucket, len(files), size, human_size(size)))

    for name, count, size, readable in table:
        print(f"{name:<15} files={count:<4} size={readable:<10}")
    print(f"{'TOTAL':<15} files={sum(c for _, c, _, _ in table):<4} size={human_size(total_bytes):<10}")
    print()

    try:
        ensure_schema()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name, to_char(pg_total_relation_size(table_schema || '.' || table_name), '9999999999') FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('bot_runs','crawl_documents','generated_posts','traffic_events','affiliate_events') ORDER BY table_name;"
                )
                rows = cur.fetchall()
                print("POSTGRES TABLES")
                print("=" * 80)
                for table_name, size in rows:
                    print(f"{table_name:<20} size={int(size or 0):,} bytes")
    except Exception as exc:
        print(f"PostgreSQL summary unavailable: {exc}")


def list_posts(days=1):
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    print(f"POSTS CREATED SINCE {since} UTC")
    print("=" * 80)
    try:
        ensure_schema()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT slug, title, topic, status, created_at, metadata
                    FROM generated_posts
                    WHERE created_at >= NOW() - (%s || ' days')::interval
                    ORDER BY created_at DESC
                    """,
                    (days,),
                )
                rows = cur.fetchall()
                if not rows:
                    print("No generated posts in that window.")
                    return
                for slug, title, topic, status, created_at, metadata in rows:
                    meta = parse_metadata_value(metadata)
                    print(f"[{created_at}] {status:<7} {topic or 'general':<20} {slug:<40} {title}")
                    if meta:
                        print(f"   metadata: {json.dumps(meta, ensure_ascii=False)[:220]}")
    except Exception as exc:
        print(f"Unable to query posts: {exc}")


def traffic_summary(days=1):
    print(f"TRAFFIC SUMMARY FOR LAST {days} DAY(S)")
    print("=" * 80)
    totals = {"impressions": 0, "clicks": 0, "conversions": 0, "revenue": 0.0}
    records = []
    try:
        ensure_schema()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT post_slug, title, source, impressions, clicks, conversions, revenue, metadata, created_at
                    FROM traffic_events
                    WHERE created_at >= NOW() - (%s || ' days')::interval
                    ORDER BY created_at DESC
                    """,
                    (days,),
                )
                rows = cur.fetchall()
                if rows:
                    for post_slug, title, source, impressions, clicks, conversions, revenue, metadata, created_at in rows:
                        totals["impressions"] += int(impressions or 0)
                        totals["clicks"] += int(clicks or 0)
                        totals["conversions"] += int(conversions or 0)
                        totals["revenue"] += float(revenue or 0.0)
                        records.append({
                            "post_slug": post_slug,
                            "title": title,
                            "source": source,
                            "impressions": impressions,
                            "clicks": clicks,
                            "conversions": conversions,
                            "revenue": revenue,
                            "created_at": created_at,
                            "metadata": parse_metadata_value(metadata),
                        })

                if not rows:
                    cur.execute(
                        """
                        SELECT bot_name, run_type, payload, created_at
                        FROM bot_runs
                        WHERE created_at >= NOW() - (%s || ' days')::interval
                        ORDER BY created_at DESC
                        """,
                        (days,),
                    )
                    rows = cur.fetchall()
                    for bot_name, run_type, payload, created_at in rows:
                        payload = payload or {}
                        if not isinstance(payload, dict):
                            continue
                        values = payload.get("traffic") or payload.get("metrics") or payload.get("analytics") or payload
                        impressions = int(values.get("impressions") or values.get("views") or 0)
                        clicks = int(values.get("clicks") or values.get("link_clicks") or 0)
                        conversions = int(values.get("conversions") or values.get("conversions_count") or 0)
                        revenue = float(values.get("revenue") or values.get("affiliate_revenue") or 0.0)
                        totals["impressions"] += impressions
                        totals["clicks"] += clicks
                        totals["conversions"] += conversions
                        totals["revenue"] += revenue
                        records.append({
                            "post_slug": payload.get("slug") or payload.get("post_slug") or bot_name,
                            "title": payload.get("title") or bot_name,
                            "source": bot_name,
                            "impressions": impressions,
                            "clicks": clicks,
                            "conversions": conversions,
                            "revenue": revenue,
                            "created_at": created_at,
                            "metadata": payload,
                        })

    except Exception as exc:
        print(f"Unable to query traffic metrics: {exc}")
        return

    print(f"impressions: {totals['impressions']}")
    print(f"clicks:     {totals['clicks']}")
    print(f"conversions:{totals['conversions']}")
    print(f"revenue:    ${totals['revenue']:.2f}")
    if totals['impressions']:
        print(f"CTR:        {(totals['clicks'] / totals['impressions']) * 100:.2f}%")
    if totals['clicks']:
        print(f"CVR:       {(totals['conversions'] / totals['clicks']) * 100:.2f}%")
    print()
    if records:
        print("MOST RECENT TRAFFIC ROWS")
        for row in records[:10]:
            print(f"[{row['created_at']}] {row['source']:<18} {row['post_slug']:<35} impressions={row['impressions']:<5} clicks={row['clicks']:<4} conv={row['conversions']:<3} revenue=${float(row['revenue'] or 0):.2f}")


def affiliate_summary(days=1):
    print(f"AFFILIATE PERFORMANCE FOR LAST {days} DAY(S)")
    print("=" * 80)
    try:
        ensure_schema()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT offer_name, offer_url, campaign, clicks, conversions, revenue, created_at, metadata
                    FROM affiliate_events
                    WHERE created_at >= NOW() - (%s || ' days')::interval
                    ORDER BY created_at DESC
                    """,
                    (days,),
                )
                rows = cur.fetchall()
                if not rows:
                    cur.execute(
                        """
                        SELECT source_name, title, url, affiliate_links, metadata, created_at
                        FROM crawl_documents
                        WHERE created_at >= NOW() - (%s || ' days')::interval
                        ORDER BY created_at DESC
                        """,
                        (days,),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        print("No affiliate records in the current time window.")
                        return
                    print("AFFILIATE OFFERS DISCOVERED")
                    for source_name, title, url, affiliate_links, metadata, created_at in rows:
                        links = affiliate_links or []
                        if isinstance(links, str):
                            try:
                                links = json.loads(links)
                            except Exception:
                                links = []
                        description = parse_metadata_value(metadata)
                        print(f"[{created_at}] {source_name:<18} {title or 'affiliate-offer'}")
                        print(f"   links={len(links) if isinstance(links, list) else 0} url={url}")
                        if description:
                            print(f"   metadata={json.dumps(description, ensure_ascii=False)[:220]}")
                    return

                total_clicks = sum(int(r[3] or 0) for r in rows)
                total_conversions = sum(int(r[4] or 0) for r in rows)
                total_revenue = sum(float(r[5] or 0.0) for r in rows)
                print(f"clicks:     {total_clicks}")
                print(f"conversions:{total_conversions}")
                print(f"revenue:    ${total_revenue:.2f}")
                if total_clicks:
                    print(f"CVR:       {(total_conversions / total_clicks) * 100:.2f}%")
                print()
                print("OFFERS")
                for offer_name, offer_url, campaign, clicks, conversions, revenue, created_at, metadata in rows[:10]:
                    print(f"[{created_at}] {campaign:<14} {offer_name:<28} clicks={clicks:<4} conv={conversions:<3} revenue=${float(revenue or 0):.2f}")
                    if offer_url:
                        print(f"   url={offer_url}")
    except Exception as exc:
        print(f"Unable to query affiliate metrics: {exc}")


def dashboard(days=1):
    summarize_storage()
    print()
    list_posts(days=days)
    print()
    traffic_summary(days=days)
    print()
    affiliate_summary(days=days)


def build_parser():
    parser = argparse.ArgumentParser(description="Anarchi-Tech ops CLI for buckets, generated posts, traffic, and affiliate conversions.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    storage_parser = subparsers.add_parser("storage", help="summarize data bucket storage and database footprint")
    storage_parser.set_defaults(func=lambda args: summarize_storage())

    posts_parser = subparsers.add_parser("posts", help="show generated posts created in a recent time window")
    posts_parser.add_argument("--days", type=int, default=1)
    posts_parser.set_defaults(func=lambda args: list_posts(days=args.days))

    traffic_parser = subparsers.add_parser("traffic", help="show post traffic summary for a recent period")
    traffic_parser.add_argument("--days", type=int, default=1)
    traffic_parser.set_defaults(func=lambda args: traffic_summary(days=args.days))

    affiliate_parser = subparsers.add_parser("affiliates", help="show affiliate offer performance")
    affiliate_parser.add_argument("--days", type=int, default=1)
    affiliate_parser.set_defaults(func=lambda args: affiliate_summary(days=args.days))

    dashboard_parser = subparsers.add_parser("dashboard", help="aggregate all storage/traffic/affiliate data")
    dashboard_parser.add_argument("--days", type=int, default=1)
    dashboard_parser.set_defaults(func=lambda args: dashboard(days=args.days))

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
