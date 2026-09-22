# AnarchI Blogger Pipeline

**Deterministic evidence. Local generation. Explicit authority. Verifiable publication.**

## Status

The AnarchI Blogger Pipeline is an evidence-driven publishing system built around deterministic contracts, explicit authority boundaries, provenance, and local generation.

**Current phase:** production-path verification → freeze → containerization

Current verified regression baseline: **286/286 tests passing.**

A green test suite is necessary but not sufficient for freeze. The remaining milestone is to prove the live Researcher, Blogger, image materializer, and upstream/downstream wiring together, then freeze those contracts before containerization.

## Pipeline

```text
Researcher
    ↓
Evidence / Search Intake
    ↓
Deterministic Source-Bundle Normalization
    ↓
Generation Admission
    ↓
Local Blogger Generation
    ↓
Reviewed Article Artifact
    ├──→ Machine Adjudication
    │        ↓
    │   Human Adjudication
    │        ↓
    │      Staged
    ↓
Editorial Visual Request
    ↓
Editorial Visual Package
    ↓
Deterministic Image Materialization
    ↓
Publication-Ready Package
```

The visual path is bound to the reviewed article. It does not independently establish factual truth or publication authority.

## Core Principles

### Evidence before assertion
Research signals become usable editorial input only through defined ingestion and normalization boundaries.

### Deterministic boundaries
Important transitions are represented by schemas, digests, validation gates, receipts, and explicit state.

### Authority is explicit
An artifact may contain evidence, provenance, or review state without receiving permission to publish.

### Provenance survives transport
Downstream artifacts retain identity bindings to the upstream material that authorized their creation.

### No silent escalation
Machine validation does not become human approval. Human review does not automatically become publication authority.

## Researcher

The current `workers/research_bot.py` intake worker:

- gathers Hacker News signals through the Algolia API
- gathers Stack Overflow signals through the Stack Exchange API
- scores observed topic clusters
- applies relevance gates
- creates candidate search-intake records
- writes `anarchi.search-intake.v1` packets
- records search audits and bot-run activity

Researcher intake is an actual upstream contract, not merely an isolated research script.

### Broader crawler path

The downstream crawler includes integrations for:

- DuckDuckGo HTML
- Bing RSS
- Stack Overflow
- GitHub Issues
- Hacker News

The GitHub integration verified in the current codebase is specifically the **GitHub Issues API**. This project does not currently claim arbitrary GitHub repository-content research from that integration.

## Source-Bundle Normalization

Ready intake is materialized into `anarchi.editorial-source-bundle.v1`.

Normalization produces:

- evidence receipts
- topic packet
- SEO plan
- sealed article input
- bridge digest
- article-input digest
- generation admission

Generation admission remains explicitly non-authoritative:

```text
factual_authority = NONE
publication_authority = NONE
approval = NONE
```

## Blogger

The Blogger performs local article generation and deterministic editorial processing.

Default local model configuration:

```text
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=granite4:tiny-h
```

The generation path:

1. retrieves normalized source material
2. requires usable evidence
3. constructs the article plan
4. generates the draft locally
5. performs deterministic quality checks
6. performs targeted repair when required
7. executes semantic review
8. constructs the reviewed article artifact
9. creates the editorial visual request
10. builds the editorial visual package
11. materializes the visual deterministically
12. validates the materialized visual
13. performs machine adjudication
14. returns the result to persistence

The normal Blogger result remains held for downstream human adjudication.

## Machine Adjudication

Contract: `anarchi.blog-machine-adjudication.v1`

Machine adjudication:

- validates the reviewed article artifact
- creates a machine receipt
- creates an adjudicated bucket
- records pass or hold disposition
- preserves the reviewed artifact digest
- grants no human authority
- grants no publication authority
- never stages an article itself

Pass disposition: `ADJUDICATED_PASS`

Hold disposition: `ADJUDICATED_HOLD`

Pending bucket: `MACHINE_ADJUDICATED_HUMAN_PENDING`

## Human Adjudication

Human adjudication is the authority boundary between machine review and staging.

It requires a valid reviewed artifact, matching machine receipt and digest, the expected machine disposition and bucket state, and an explicit human disposition.

Only explicit human approval can move an article toward staging.

## Visual System

The visual system is separated into request, package, transport, and materialization boundaries.

### Editorial Visual Request

Factual visuals use:

```text
visual_purpose = FACTUAL
```

Current policy: every successfully verified reviewed article receives one factual visual bound to its material claims.

Visual representation may not introduce, strengthen, or change claims.

### Editorial Visual Package

The package carries reviewed article identity, article digest, reviewed article text, bound claims, visual request, visual handoff, package digest, and authority state.

Bound claims are projections of the reviewed article, not a second evidence system.

### Deterministic Image Materialization

Contract: `anarchi.blogger-visual-materializer.v1`

Renderer: `blogger-deterministic-visual-v1`

Runtime: `python-stdlib-local`

Artifact format: **SVG**

The materializer consumes an already validated visual package, creates the local artifact, records package and asset digests, records renderer/runtime identity, validates the artifact, and grants no evidentiary, human-approval, or publication authority.

It does not mutate the reviewed article, mutate the visual package, or call external services.

## Persistence

The database layer coordinates persistence and lifecycle state for search intake, packets, generation admission, generation jobs, generation results, bot-run records, and staging.

Database storage does not itself constitute publication authority.

## Docker Compose

Current Compose topology includes:

```text
postgres
anarchi-engine
research-bot
outreach-bot
crawler-bot
compiler-bot
ollama
model-loader
wide-search-crawler
dedup-engine
seo-bundle-gen
llm-blogger
publisher-bot
cloudflared
postgres_data
ollama_data
anarchi-spine
```

Containerization is the runtime packaging layer, not the architectural proof layer.

The intended sequence is:

```text
prove live path → freeze contracts → freeze wiring → containerize
```

## Repository Layout

```text
.
├── data/
├── services/
├── test/
├── workers/
│   ├── blog_loop/
│   ├── research_bot.py
│   ├── crawler_bot.py
│   ├── llm_blogger.py
│   ├── publisher_bot.py
│   ├── blog_visual_materializer.py
│   └── editorial_*.py
├── docker-compose.yml
├── EDITORIAL_PIPELINE.md
└── BLOG_MARKET_VISUAL_LOOP_ARCHITECTURE.md
```

## Testing

The repository currently contains **42 test files**.

Verified regression baseline:

```text
Ran 286 tests
OK
FULL_REGRESSION_EXIT=0
```

Targeted visual, editorial, machine-adjudication, and human-adjudication tests are maintained around their respective contracts.

Green tests establish regression safety. They do not by themselves prove the deployed workers are performing the intended end-to-end work.

## Development Workflow

```text
Inspect
  ↓
Trace
  ↓
Implement
  ↓
Compile
  ↓
Targeted tests
  ↓
Full regression
  ↓
Live-path proof
  ↓
Freeze
  ↓
Containerize
```

## Production-Proof Target

Before freezing, prove four areas together:

### 1. Researcher

Prove signal collection, scoring, search-intake creation, packet emission, and audit recording.

### 2. Blogger

Prove normalized input, local generation, reviewed artifact creation, provenance preservation, machine adjudication, and absence of silent publication authority.

### 3. Image Materializer

Prove visual request creation, package creation, deterministic materialization, validation, package identity preservation, and authority remaining `NONE`.

### 4. Wiring

Prove upstream packets reach intended consumers, generation jobs are admitted correctly, lifecycle transitions are coherent, adjudication receives the exact reviewed artifact, human adjudication remains the staging authority, and publisher behavior respects the authority boundary.

## Freeze Criteria

Freeze when:

- the live Researcher path is proven
- the live Blogger path is proven
- the live visual path is proven
- upstream and downstream wiring are proven
- provenance survives the complete path
- authority remains explicit at every boundary
- targeted tests remain green
- the full regression suite remains green
- no unexplained lifecycle transitions remain

After freeze, containerization should package the proven system rather than introduce new architectural uncertainty.

## Security and Trust Boundary

**Being able to create an artifact is not the same thing as being authorized to publish it.**

Research produces evidence.

Generation produces proposed editorial content.

Validation produces deterministic findings.

Machine adjudication produces a machine disposition.

Human adjudication controls the human approval boundary.

Visual materialization represents already-reviewed material.

Publication remains downstream of explicit authority.

## Related Documentation

- `EDITORIAL_PIPELINE.md`
- `BLOG_MARKET_VISUAL_LOOP_ARCHITECTURE.md`
- `docker-compose.yml`

## Project Direction

The immediate goal is not to add more components.

The immediate goal is to prove the components already present, freeze their contracts and wiring, and then containerize the resulting system.

The system should become smaller in uncertainty before it becomes larger in deployment.

---

**Truth verified. Trust earned.**

