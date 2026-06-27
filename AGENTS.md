# AGENTS.md

## Project mission

This repository implements an attention-budgeted event intelligence system for ordinary Nasdaq-100 / US technology-stock investors.

The product is not a trading terminal, not a buy/sell signal engine, and not an investment adviser. It is an evidence-grounded information-prioritization system: collect many sources, consolidate them into events, verify claims against source evidence, rank the events, and generate a low-stress daily brief of roughly 4-5 items per user.

The research direction behind the product is Budgeted Event-Evidence Sufficiency for Search Agents: a search agent should know when the current evidence is sufficient, when to keep searching, and when to abstain under explicit query/read/token budgets.

## Core product principles

1. Attention budget first: prefer fewer, higher-value event cards over a real-time news stream.
2. Event-first, not article-first: merge duplicate articles and updates into stable event objects.
3. Evidence-first: every factual conclusion should map to a claim and supporting evidence span.
4. Source-aware: distinguish SEC/regulator, company IR, press release, transcript, mainstream media, analyst opinion, aggregator, and social rumor.
5. Time-aware: track `published_at`, `retrieved_at`, `event_time`, and whether evidence has been superseded.
6. Budget-aware: do not run expensive open-ended agents per user. Use a global event engine plus cached event cards and lightweight user reranking.
7. No investment advice: never produce buy/sell/hold recommendations, target-price conclusions, portfolio instructions, or promised returns.

## Target architecture

Use this pipeline as the architectural source of truth:

```text
Source Registry
  -> Deterministic Ingestion
  -> Document Normalization
  -> Retrieval + Dedup
  -> Global Event Engine
  -> Claim-Evidence Ledger
  -> Sufficiency / Conflict / Temporal Validity Checks
  -> Conditional Search Agent
  -> Global Importance Ranking
  -> Per-user Watchlist Reranking
  -> Daily Brief Generation
```

The key domain objects are:

```text
Document -> Chunk / Span -> Event -> Claim -> Evidence -> EventCard -> Briefing
```

The core technical asset is the Claim-Evidence Ledger, not the UI and not the agent framework.

## Recommended repository layout

Create or preserve a monorepo layout close to this:

```text
apps/
  api/                  # FastAPI service
  web/                  # Next.js frontend
packages/
  core/                 # shared Python domain models and schemas
  ingestion/            # source registry, fetchers, parsers
  retrieval/            # BM25/dense/hybrid retrieval, reranking
  events/               # event clustering, dedup, event relations
  evidence/             # claim extraction, evidence span linking, sufficiency checks
  agent/                # LangGraph state machine and agent tools
  ranking/              # global scoring, MMR, user rerank
  briefing/             # event card and daily brief generation
pipelines/
  dagster/              # scheduled assets/jobs for ingestion and event pool generation
research/
  benchmarks/           # frozen corpora, eval specs, baselines
  experiments/          # reproducible experiment scripts
infra/
  docker/               # local infra definitions
  migrations/           # database migrations
configs/                # non-secret config templates
docs/                   # design docs, source policies, schema notes
tests/                  # integration and cross-package tests
```

If the actual repository structure already differs, inspect it first and adapt to the existing layout instead of creating duplicate parallel folders.

## Preferred stack

Backend and research:
- Python 3.11+
- FastAPI for API services
- Pydantic for all structured inputs/outputs
- SQLAlchemy or SQLModel for database access
- Alembic for migrations
- PostgreSQL as the system-of-record database
- pgvector for early vector retrieval in product mode
- Pyserini for reproducible research retrieval baselines
- Dagster for deterministic data pipelines
- LangGraph for stateful conditional agent workflows
- LiteLLM or an equivalent gateway for model-provider abstraction

Frontend:
- Next.js + TypeScript
- Server-side rendering where useful
- Keep frontend logic thin; core event/evidence logic belongs in backend packages

Infrastructure:
- Docker Compose for local development
- S3-compatible object storage or MinIO for raw documents and parsed artifacts
- Redis only when caching is needed
- Do not introduce Kafka, Kubernetes, Neo4j, or a distributed workflow engine until there is a demonstrated need

Observability:
- Record agent runs, queries, retrieved documents, read documents, model names, prompt versions, token counts, latency, cost, stop decisions, and final citations
- Prefer structured logs over free-form logs

## Data model requirements

Use explicit schema objects. Avoid passing untyped dictionaries through the core pipeline.

Minimum `Document` fields:

```text
doc_id
source_id
source_type
source_tier
source_family_id
title
url
published_at
retrieved_at
raw_object_uri
content_hash
parser_version
language
entities
```

Minimum `Event` fields:

```text
event_id
canonical_title
event_type
entities
event_time
status: new | developing | corrected | refuted | resolved
related_doc_ids
claim_ids
evidence_status: sufficient | insufficient | conflicting | abstained
```

Minimum `Claim` fields:

```text
claim_id
event_id
claim_text
claim_type: fact | forecast | opinion | rumor
mandatory: bool
status: supported | refuted | missing | conflicting | obsolete
```

Minimum `EvidenceSpan` fields:

```text
span_id
doc_id
claim_id
relation: support | refute | update | uncertain
text
char_start
char_end
source_type
source_tier
source_family_id
published_at
valid_from
valid_to
confidence
```

Never generate a user-facing factual sentence that cannot be traced back to one or more claim/evidence IDs.

## Agent design rules

The agent is conditional and bounded. It should only run when deterministic retrieval and verification indicate a real evidence gap, conflict, or high-value uncertainty.

Allowed agent actions should remain finite and auditable:

```text
SEARCH_PRIMARY_SOURCE
SEARCH_INDEPENDENT_CONFIRMATION
SEARCH_UPDATE_OR_CORRECTION
READ_DOCUMENT
EXTRACT_CLAIMS
VERIFY_EVIDENCE
CHECK_SOURCE_INDEPENDENCE
CHECK_TEMPORAL_VALIDITY
STOP
ABSTAIN
```

Every agent run must include explicit budgets:

```text
query_budget
read_budget
token_budget
latency_budget_ms
```

Stop only when mandatory claims are covered, key conflicts are resolved or explicitly marked unresolved, evidence is temporally valid, and marginal expected evidence gain is lower than search cost. Abstain when evidence remains insufficient after budget exhaustion.

Do not implement open-ended autonomous browsing as a default behavior.

## Ranking rules

Ranking must separate:

1. Global event importance
2. Evidence confidence
3. User relevance
4. Diversity / redundancy control

Initial ranking should be interpretable: rules, LightGBM/XGBoost, MMR, or other transparent listwise selection are preferred over an opaque LLM-only ranker.

Useful global ranking signals:

```text
source_confidence
novelty
scope
materiality
urgency
market_confirmation
impact_channel
rumor_risk
unresolved_conflict
```

Useful user reranking signals:

```text
watchlist_overlap
holding_overlap_optional
sector_preference
reading_feedback
ignore_feedback
topic_fatigue
```

The system recommends information priority, not investment actions.

## Brief generation rules

Briefs should be generated from structured event cards, not directly from raw news.

Each event card should include:

```text
what happened
companies involved
evidence sources and source tiers
why it might matter
impact mechanism tags
uncertainties / missing evidence
whether to continue monitoring
user relevance explanation
```

Forbidden output:
- Buy/sell/hold instructions
- Guaranteed or implied return claims
- Unverified rumors presented as facts
- Analyst opinions rewritten as confirmed facts
- Price targets as system conclusions

## Research mode vs product mode

Research mode must be reproducible:

```text
fixed corpus snapshot
fixed index version
fixed model version
fixed prompt version
fixed budgets
stored trajectories
stable evaluation scripts
```

Product mode may be live, but should still preserve raw documents, parsed artifacts, model metadata, and run traces for auditing.

Do not mix live-web-only behavior into the main research benchmark path.

## Data-source and compliance rules

1. Prefer APIs, RSS, SEC EDGAR, company IR, and other permitted sources over scraping.
2. Track source license and redistribution policy in the Source Registry.
3. Do not store or redistribute copyrighted full text unless the source license permits it.
4. For restricted news sources, store URL, metadata, timestamps, hashes, and derived annotations where appropriate; avoid mirroring full articles.
5. Social media should be used only as a weak signal or lead source unless independently verified.
6. Do not implement features that route users to brokers, automate trades, or provide individualized investment advice.

## Development workflow for Codex

Before editing:
- Inspect the existing repository structure.
- Read this file and any package-level AGENTS.md files.
- Identify the smallest safe change that satisfies the task.
- Avoid broad rewrites unless explicitly requested.

While editing:
- Keep domain logic in backend/core packages, not in notebooks or frontend components.
- Use typed models and explicit schemas.
- Add or update tests with every behavioral change.
- Prefer deterministic functions for ingestion, parsing, event clustering, and evidence checks.
- Keep LLM prompts versioned and testable.
- Do not commit secrets, API keys, raw credentials, or local `.env` files.

After editing:
- Run the most relevant tests and linters available.
- If a command is missing or fails because the project is not initialized yet, state that clearly in the final summary.
- Summarize changed files, behavior changes, tests run, and remaining risks.

## Expected commands

Use the actual project commands if they already exist. If not, initialize toward the following conventions.

Python:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Frontend:

```bash
pnpm install
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Local services:

```bash
docker compose up -d postgres minio redis
```

Migrations:

```bash
uv run alembic upgrade head
```

Do not claim tests passed unless they were actually run.

## Code style

Python:
- Prefer pure functions for pipeline transforms.
- Use Pydantic models at system boundaries.
- Use timezone-aware datetimes.
- Avoid global mutable state.
- Avoid hidden network calls in constructors or import paths.
- Keep parsing, retrieval, ranking, and generation modules separate.

TypeScript:
- Use strict TypeScript.
- Keep API types generated or mirrored from backend schemas where possible.
- Keep UI components presentation-focused.

SQL:
- Use migrations for schema changes.
- Keep event, claim, evidence, and provenance tables queryable and auditable.
- Avoid destructive migrations without explicit approval.

## Initial MVP scope

Build first:

1. Source Registry
2. SEC / IR / press-release ingestion skeletons
3. Document normalization and chunk/span representation
4. Basic BM25 / vector retrieval interface
5. Event object schema and simple clustering
6. Claim-Evidence Ledger schema
7. Sufficiency checker stub with rule-based logic
8. Conditional agent state machine skeleton
9. Event card generator from structured fields
10. Daily brief endpoint and minimal UI

Do not build first:

- Real-time trading signals
- Full social-media monitoring
- Automated portfolio advice
- Mobile app
- Complex GraphRAG
- Multi-agent teams
- Full Kubernetes deployment
- Custom financial LLM training

## Acceptance criteria for early tasks

A change is acceptable when it:

1. Preserves the Document -> Event -> Claim -> Evidence model.
2. Keeps source provenance and timestamps intact.
3. Has tests or a clear reason tests are not yet possible.
4. Does not introduce unbounded agent behavior.
5. Does not weaken compliance boundaries around investment advice.
6. Does not add unnecessary infrastructure.
7. Keeps the MVP path simple and reproducible.

## If uncertain

Prefer the narrower, auditable, reproducible implementation. Ask for clarification before introducing new infrastructure, changing the domain model, or adding external data sources with unclear licensing.
