# Anarchi Editorial and Revenue Pipeline

## Outcome

The active pipeline turns evidence-backed engineering search opportunities into a deep queue of source-grounded posts. It may construct as many posts as the source material and local compute can support, while publishing no more than two or three per day. Publication creates an immutable artifact and appends a market-data packet for the downstream data-to-graphic materializer.

No external LLM API is used. Editorial planning and section drafting run through the local Ollama-hosted `granite4:tiny-h` 7B-A1B hybrid mixture-of-experts model. The smaller `granite3-moe:3b` model can remain installed as a recovery model, but it is not the publication-quality default.

## Dataflow

```text
public trend/problem signals
          |
          v
  research-bot
  query scoring + SEO plan + search audit
          |
          v
  append-only packet bucket <----------------------+
          |                                         |
          v                                         |
  crawler-bot                                       |
  DuckDuckGo + Stack Overflow + GitHub + HN         |
  bounded excerpts + metrics + image references ----+
          |
          v
  outreach-bot (observer; never consumes packets)
  product/service research + affiliate candidates
  + contextual ad campaign candidates
          |
          v
  llm-blogger finalizer
  atomically serializes all packets into a durable
  generation job and drains only the active view
          |
          v
  local MoE: evidence plan -> section specialists -> deterministic assembly and QA
             -> repair pass when necessary
          |
          v
  staged publication queue (may contain hundreds)
          |
          v
  publisher-bot: 2-3 configured slots per day
          |
          +--> immutable artifact + indexed Markdown
          |
          +--> append-only market_data_bucket
                     |
                     v
             data > graphic materializer
```

## Bucket semantics

- `packet_bucket` is append-only for the intake, crawler, and monetization workers.
- `observer_offsets` proves what the monetization worker observed without removing anything.
- The finalizer copies every associated active packet into `generation_queue.source_bundle` in one database transaction.
- The same transaction marks those packets consumed. This empties `active_packet_bucket`, but it does not delete evidence.
- Failed or unavailable model inference does not lose source material: the serialized generation job remains queued and is retried up to five times.
- `generation_queue.state = staged` is the publication backlog. Construction and publication rates are intentionally independent.

## Intake scope and evidence

The configured clusters in `data/config/intake_policy.json` focus on high-consequence engineering problems with plausible enterprise purchase intent:

- local MoE inference, RAG evaluation, latency, memory, and quantization;
- cloud-native reliability, Kubernetes cost, eBPF, and OpenTelemetry;
- software supply-chain security, SBOM, SLSA, zero trust, and CI/CD;
- PostgreSQL, high-concurrency databases, connection pools, and vector indexes;
- Node.js/TypeScript production failures and high-traffic APIs;
- wallet and smart-contract security aligned with WSRS.

The intake calculates traffic, trend, problem, and commercial-intent scores. Traffic and commercial values are documented proxies from public engagement plus policy weights. They are **not** called measured search volume, keyword difficulty, CPC, or conversion value. Actual measurements require Search Console and/or a licensed keyword-data source.

Every research cycle writes a timestamped `data/search_audits/search_audit_*.json` file containing the selected queries, scores, source URLs, observed engagement, SEO plan, and any source errors.

## SEO quality policy

The system follows people-first constraints instead of manufacturing search-engine-first articles:

- titles are distinct, descriptive, concise, and limited to 70 characters;
- the primary query is used naturally rather than repeated mechanically;
- every post must diagnose a real problem, teach implementation, show verification, and discuss trade-offs;
- factual claims must cite URLs from the serialized source bundle;
- a deterministic gate checks length, heading depth, code/command examples, supported citations, and source-copy overlap;
- article metadata contains `BlogPosting` intent, a bounded meta description, source URLs, relevant hashtags, and image references;
- images with unknown licensing remain references only; the publisher must use original or licensed assets with descriptive filenames and alt text;
- automation and model lineage are retained in artifact metadata.

Primary guidance used for these controls:

- [Google: Creating helpful, reliable, people-first content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)
- [Google: Influencing title links](https://developers.google.com/search/docs/appearance/title-link)
- [Google: Image SEO best practices](https://developers.google.com/search/docs/appearance/google-images)
- [Google: Article structured data](https://developers.google.com/search/docs/appearance/structured-data/article)

## Monetization rules

- The monetization worker observes the same evidence bucket as the crawler; it does not consume source packets.
- Product/service matches are ranked by topical relevance and a catalog payout proxy.
- An opportunity is publishable as an affiliate link only when `affiliate_verified` is explicitly true in `data/affiliates.json`.
- Current catalog entries are deliberately marked unverified. UTM parameters are not proof of a material affiliate relationship.
- Unverified opportunities may inform partnership outreach or editorial context, but the LLM cannot publish their links as affiliate links.
- Ad campaign candidates are labeled modeled, not measured, and remain separate from editorial evidence.
- Advertising must be visibly distinguished from editorial content, and material relationships require disclosure.

## Publication and artifact lifecycle

Defaults use `America/Chicago` and three slots: `08:15`, `13:15`, and `18:15`.

```dotenv
DAILY_PUBLISH_LIMIT=3
PUBLISH_TIMEZONE=America/Chicago
PUBLISH_SLOTS=08:15,13:15,18:15
```

Set `DAILY_PUBLISH_LIMIT=2` to run two posts per day. The publisher never exceeds three, even if a larger value is supplied. When the service is down during a slot, it may catch up later that same day without exceeding the daily limit.

On publication:

1. Markdown is written atomically to `data/posts/<slug>.md`.
2. The database inserts a content-addressed artifact.
3. A trigger rejects every later update or deletion of that artifact row.
4. `data/artifacts/index.json` is rebuilt as the searchable artifact index.
5. A content-addressed packet is appended to `market_data_bucket` and mirrored under `data/market_bucket/`.

The market packet includes artifact identity, content hash, query and topic data, hashtags, source URLs, affiliate/ad observations, image references, a graphic brief, and explicit truth/publication constraints.

## Local MoE profile

The WSL host currently exposes about 7.5 GiB of RAM. `granite4:tiny-h` is a 7B-A1B hybrid MoE whose Ollama artifact is about 4.2 GB, leaving a narrow but workable envelope for PostgreSQL, crawlers, the site, and the illustration stack when inference is serialized. The compose model loader pulls it once into the persistent Ollama volume.

Generation is intentionally serialized (`OLLAMA_NUM_PARALLEL=1`, one generation job per cycle) to prevent memory pressure. The orchestrator owns the evidence plan, headings, assembly, source allowlist, counts, fence validation, and release state. The MoE writes bounded sections, and targeted repair adds only missing material instead of asking the model to rewrite an entire article.

## Operations

Start the active services from WSL:

```sh
cd "/mnt/c/duel engine devstack blog building"
docker compose up -d --build
```

The legacy compiler, wide crawler, old dedup worker, and old SEO bundle worker are available only with the `legacy` profile and should not run beside the packet pipeline.

Queue inspection:

```sql
SELECT state, count(*) FROM intake_queries GROUP BY state ORDER BY state;
SELECT count(*) FROM active_packet_bucket;
SELECT state, count(*) FROM generation_queue GROUP BY state ORDER BY state;
SELECT published_at, artifact_id, slug FROM artifacts ORDER BY published_at DESC;
SELECT count(*) FROM market_data_bucket WHERE observed_at IS NULL;
```

Run any worker once for controlled diagnosis by setting `RUN_ONCE=1` for a one-off container. The worker logs and the audit JSON files contain counts and safe metadata; source bundles remain in PostgreSQL.
