# Blog + Market + Visual Loop Architecture

## Status and scope

This construction wave adds an isolated, deterministic contract package at
`workers/blog_loop`. It is not imported by the running workers, registered in
Docker Compose, connected to a provider, attached to the database, or capable
of publishing. The package proves payload identity, lineage, validation, and
authority containment before humans wire any ecosystem seam.

The causal order is preserved:

`live demand → niche relevance → retrieved evidence → topic qualification → article candidate → claim review → affiliate candidates → SEO validation → existing human/publication authority → publication receipt → telemetry → image opportunity → image request → image plan → image candidate → review → optional deployment → comparison telemetry`

No arrow carries implicit authority. Each crossing binds a canonical SHA-256
digest and the downstream validator recomputes identity from payload.

## Components

`core.py` defines canonical JSON identity, receipt sealing, exact-field checks,
timestamp/URL/digest validation, and the common zero-authority invariant.
Malformed or mutated payloads fail closed.

`editorial.py` defines live/derived/model/historical keyword observations,
versioned niche assessments, independent freshness and topic alignment,
qualified topic packets, article-worker inputs, dual-relevance affiliate
candidates, and separate SEO plan/validation receipts. Provider metrics are an
opaque observed map; unavailable values remain absent rather than synthesized.
Affiliate program observations separately bind disclosed commission, cookie,
EPC, conversion, refund, and payout terms. Deterministic ranking places topic-
eligible products first and uses net EPC only when it was actually observed;
unknown economics remain `UNKNOWN`, not zero, and ranking grants no CTA authority.

`market_visual.py` defines a receipt for publication performed by a future
authorized adapter, append-only compatible telemetry, a deterministic image
opportunity recommendation, pull/push requests, bounded visual plans,
materialized candidates, a withheld visual-review interface, and non-causal
before/after comparisons.

`adapters.py` contains provider-neutral protocols only. It performs no I/O.
Concrete search, SERP, affiliate, analytics, publication, and image adapters are
manual integration work.

`contracts.manifest.json` inventories the schemas, digest fields, authority
states, activation state, and system-wide invariants.

## Existing components and reuse

The existing `editorial_claims.py`, `editorial_evidence.py`,
`editorial_verifier.py`, `editorial_review_contract.py`, and
`editorial_review_artifact.py` already enforce the distinction between
retrieval, verification, review, and authority. They remain unchanged and are
the intended future article-review seam.

The existing `editorial_visual_request.py`, `editorial_visual_package.py`, and
`editorial_visual_transport.py` already preserve reviewed-article truth across
the Foundry-to-visual boundary. They remain unchanged and are the intended
future conversion target for a validated blog image request.

The existing `pipeline_core.py` canonicalization ideas were reused conceptually,
but not modified. The new core deliberately uses native Python only and does
not inherit its network helpers.

## Conflicting legacy paths

`services/compiler/factory.ts` contains fallback affiliate selection and CTA
injection. `services/analytics/feedback.js` can rotate CTA layout and swap the
affiliate mix from revenue telemetry. `publisher_bot.py` can publish staged
jobs on time slots. These paths are historical runtime behavior, conflict with
this wave's authority boundaries, and were not called, edited, or wired to the
new contracts.

`crawler_bot.py`, `research_bot.py`, `outreach_bot.py`, and `llm_blogger.py`
contain useful acquisition and materialization behavior but currently use
runtime database states rather than these frozen receipts. They require manual
adapter work; importing the new modules into them is intentionally deferred.

## Failure behavior

- A live keyword without provider-bound raw observation fails.
- Retrieval time never substitutes for source publication/update time.
- Unknown source dates produce `UNKNOWN`, not `CURRENT`.
- Only `IN_NICHE` may qualify a topic automatically.
- Current-required topics reject stale or unknown evidence.
- Affiliate eligibility requires both niche and article relevance, known
  availability, and a valid destination.
- SEO checks cannot create evidence, truth, approval, or publication authority.
- Telemetry accepts only declared provider metric names and stays append-only.
- Image opportunity is recommendation-only; missing imagery never forces work.
- Pull and push image requests grant no generation or insertion authority.
- Materialized bytes remain a candidate with no approval.
- R16 applicability is `DEFERRED`; automated positive visual authority is
  withheld and human review remains required.
- Before/after output states association and observed change only, never
  causality.

## Manual insertion points

1. A search-demand adapter must translate provider output into keyword receipts.
2. A SERP/evidence adapter must bind dates and content digests without treating
   retrieval as truth.
3. The topic packet must be transformed into the existing claim-review input
   without bypassing Atomic Reviewer.
4. Affiliate discovery must emit candidates; CTA construction remains a
   separate human-authorized action.
5. SEO plans and checks may annotate a candidate but may not promote it.
6. A publisher adapter may produce a publication receipt only after validating
   existing human approval and publication authority.
7. An analytics adapter must bind provider, property, post, and observation
   window and append new receipts.
8. A blog image request must be translated into the existing editorial visual
   package/transport boundary.
9. Image materialization must return pixels and execution lineage only.
10. R16 or a successor may later be inserted at the review interface; until
    then the positive path is human review.

## Known limitations

No live search, SEO-metric, affiliate, analytics, publication, or image provider
was available or invoked in this wave. No database persistence adapter or
uniqueness store was built; replay uniqueness is represented by idempotency
fields and must be enforced transactionally by the future publication adapter.
The opportunity heuristic is deliberately bounded and not a learned optimizer.
It cannot establish causal impact. Automated visual perception is not required
for text-first publication and does not supply positive authority.
