# AGENTS.md

## Project Mission

This repository implements an attention-budgeted event intelligence system for ordinary Nasdaq-100 / US technology-stock investors.

The product is not a trading terminal, not a buy/sell signal engine, and not an investment adviser. It is an evidence-grounded information-prioritization system: collect many permitted sources, consolidate them into events, verify factual claims against source evidence, rank the events, and generate a low-stress daily brief of roughly 4-5 items per user.

The research direction is Budgeted Event-Evidence Sufficiency for Search Agents: a search agent should know when current evidence is sufficient, when to keep searching, and when to abstain under explicit query/read/token/latency budgets.

## Architectural Constitution

Use this pipeline as the architectural source of truth:

```text
Source Registry
  -> Deterministic Ingestion
  -> RawStore + RunManifest
  -> Document / Chunk / Span
  -> LLM-Assisted Extraction
  -> Deterministic Validation
  -> Claim-Evidence Ledger
  -> Sufficiency / Conflict / Temporal Validity Checks
  -> Super Bear Tool/API Surface
  -> External Investigator Harness
  -> Deterministic Result Validation
  -> Ranking + Diversity Control
  -> EventCard / Daily Brief
```

The key domain objects are:

```text
Document -> Chunk / Span -> Event -> Claim -> EvidenceSpan -> EventCard -> Briefing
```

The core technical asset is the Claim-Evidence Ledger, not the UI, not the agent framework, and not any single model provider.

## Core Product Principles

1. Attention budget first: prefer fewer, higher-value event cards over a real-time news stream.
2. Event-first, not article-first: merge duplicate articles and updates into stable event objects.
3. Evidence-first: every factual conclusion must map to a claim and one or more supporting evidence spans.
4. Source-aware: distinguish SEC/regulator, company IR, press release, transcript, mainstream media, analyst opinion, aggregator, and social rumor.
5. Time-aware: track `published_at`, `retrieved_at`, `event_time`, and whether evidence has been superseded.
6. Budget-aware: do not run open-ended agents per user. Use a global event engine plus cached event cards and lightweight user reranking.
7. Harness-resilient: external agent harness upgrades should change adapters, not the provenance ledger or core schemas.
8. Model-resilient: model upgrades should change model routing, prompts, and extraction quality, not the provenance ledger or core schemas.
9. No investment advice: never produce buy/sell/hold recommendations, target-price conclusions, portfolio instructions, or promised returns.

## LLM Boundary

LLMs may propose structured candidates, but deterministic validation and the Claim-Evidence Ledger decide what becomes a system fact.

LLMs may:

```text
extract entity candidates
extract event candidates
draft claim candidates
find evidence-span candidates
label document sections
summarize structured event cards
judge sufficiency or conflict inside a bounded evidence pack
```

LLMs must not:

```text
invent source provenance
generate stable IDs without deterministic checks
decide source license or storage policy
turn search snippets, social sentiment, or price movement into primary evidence
write user-facing factual sentences without claim/evidence IDs
perform unbounded browsing
produce investment advice
state that one event caused a price move unless the evidence explicitly supports that relation
```

Use low-cost models for broad schema-bound extraction. Use stronger models only for high-value adjudication, conflicts, sufficiency checks, abstention decisions, and final compliance review.

## External Agent Harness Boundary

Super Bear should not depend on one self-built agent framework. External tools such as Claude Code, GitHub Copilot CLI, OpenCode, Kilo Code, nanobot, Langcli, future GPT-based agents, or other harnesses are replaceable execution environments for the same bounded investigator contract.

Super Bear Core owns:

```text
source registry
raw store
document / chunk / span access
claim-evidence ledger
validation
budgets
audit records
final ledger commits
```

External harnesses may:

```text
call approved Super Bear tools
search approved source families
read documents and chunks
propose claims
propose evidence spans
propose sufficiency / conflict / abstain decisions
return structured investigation results
```

External harnesses must not:

```text
write directly to the Claim-Evidence Ledger
bypass deterministic result validation
ignore query/read/token/latency budgets
use tools outside the allowed action list
invent source provenance
produce final user-facing facts without evidence IDs
```

Expose Super Bear Core in this order:

```text
1. Python API
2. CLI wrapper: stdin JSON -> stdout JSON
3. MCP server, when tool contracts stabilize
4. HTTP API, when product services need it
5. harness-specific skill/plugin packages, only as thin adapters
```

The stable contract is the tool schema and result schema, not any particular harness.

## Recommended Repository Layout

Create or preserve a monorepo layout close to this:

```text
apps/
  api/                  # FastAPI service, product mode
  web/                  # Next.js frontend, product mode
packages/
  core/                 # shared Python domain models and schemas
  ingestion/            # source registry, fetchers, parsers, raw store
  extraction/           # LLM-assisted candidate extraction
  tools/                # callable Super Bear tools for external harnesses
  retrieval/            # BM25/dense/hybrid retrieval, later
  events/               # event assembly, dedup, event relations
  evidence/             # claims, evidence spans, sufficiency checks
  harness/              # external harness adapters, CLI/MCP/http wrappers
  ranking/              # global scoring, MMR, user rerank
  briefing/             # event cards and daily brief generation
pipelines/
  dagster/              # scheduled assets/jobs, later
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

## Preferred Stack

Early MVP, optimized for a 2-3 day auditable loop:

```text
Python 3.11+
Pydantic for structured models
YAML for non-secret configuration
JSONL for portable pipeline outputs
filesystem RawStore
CLI runner
pytest
versioned prompts
ModelRun records
InvestigatorRun records
low-cost LLM for extraction
stronger LLM for bounded adjudication
Python API and CLI wrappers for tools
```

Product mode, only after the JSONL loop proves useful:

```text
FastAPI
PostgreSQL
SQLAlchemy or SQLModel
Alembic
pgvector when retrieval scale justifies it
S3-compatible object storage or MinIO
Dagster for deterministic scheduled pipelines
LiteLLM or equivalent model gateway
MCP server when tool contracts stabilize
LangGraph or another harness only when durable multi-step state is needed
structured observability
```

Do not introduce Kafka, Kubernetes, Neo4j, complex GraphRAG, multi-agent teams, or a distributed workflow engine until there is a demonstrated need.

Redis is allowed only when caching or background-job pressure actually exists.

## Data Model Requirements

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

Minimum `Chunk` / `Span` fields:

```text
chunk_id or span_id
doc_id
text
char_start
char_end
section_label
content_hash
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

Minimum `ModelRun` fields:

```text
model
prompt_version
input_tokens
output_tokens
cache_hit_tokens
cache_miss_tokens
cost_estimate
latency_ms
schema_validation_status
source_doc_ids
output_object_ids
```

Minimum `InvestigatorRun` fields:

```text
investigator_run_id
harness_name
harness_version
adapter_version
model_name
prompt_version
allowed_actions
query_budget
read_budget
token_budget
latency_budget_ms
input_event_ids
input_claim_ids
input_evidence_span_ids
tool_calls
output_object_ids
stop_reason
abstained
validation_status
```

Never generate a user-facing factual sentence that cannot be traced back to one or more claim/evidence IDs.

## Investigator Harness Rules

The investigator is a bounded contract that may be implemented by an external harness. It should only run when deterministic retrieval and verification indicate a real evidence gap, conflict, temporal-validity issue, or high-value uncertainty.

Allowed harness actions must remain finite and auditable:

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

Every investigator run must include explicit budgets:

```text
query_budget
read_budget
token_budget
latency_budget_ms
```

Stop only when mandatory claims are covered, key conflicts are resolved or explicitly marked unresolved, evidence is temporally valid, and marginal expected evidence gain is lower than search cost.

Abstain when evidence remains insufficient after budget exhaustion.

Do not implement open-ended autonomous browsing as a default behavior.

Harness output is advisory until Super Bear validates it. New claims, evidence spans, events, sufficiency decisions, and event cards must pass deterministic result validation before they can update the Claim-Evidence Ledger.

## Ranking Rules

Ranking must separate:

1. Global event importance
2. Evidence confidence
3. User relevance
4. Diversity / redundancy control

Initial ranking should be interpretable: rules, MMR, or other transparent listwise selection are preferred over opaque LLM-only ranking.

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

Market movement is allowed only as context or confirmation. It must not become trading advice or unsupported causal attribution.

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

## Brief Generation Rules

Briefs must be generated from structured event cards, not directly from raw news.

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
- Unsupported causal claims about price movement

## Research Mode vs Product Mode

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

## Data-Source and Compliance Rules

1. Prefer APIs, RSS, SEC EDGAR, company IR, and other permitted sources over scraping.
2. Track source license and redistribution policy in the Source Registry.
3. Do not store or redistribute copyrighted full text unless the source license permits it.
4. For restricted news sources, store URL, metadata, timestamps, hashes, and derived annotations where appropriate; avoid mirroring full articles.
5. Social media should be used only as a weak signal or lead source unless independently verified.
6. Do not implement features that route users to brokers, automate trades, or provide individualized investment advice.

Minimum Source Registry policy fields:

```text
license_type
storage_allowed
redistribution_allowed
full_text_allowed
derived_only
rate_limit_policy
source_tier
source_family_id
```

## Initial MVP Scope

Build first:

1. Source Registry
2. Deterministic ingestion for SEC / IR / press-release skeletons
3. RawStore + RunManifest
4. Document normalization and Chunk / Span representation
5. LLM-assisted extraction skeleton with versioned prompts
6. Deterministic validation for schema, timestamps, source tier, source family, and char offsets
7. Event schema and deterministic event assembler
8. Claim-Evidence Ledger schema
9. Sufficiency / conflict / temporal-validity checker stub
10. Super Bear tool functions for read-only document, chunk, claim, and evidence access
11. CLI wrapper for the investigator contract: stdin JSON -> stdout JSON
12. Deterministic result validator for harness outputs
13. EventCard generator from structured fields
14. Daily brief Markdown or HTML output

Do not build first:

- Real-time trading signals
- Full social-media monitoring
- Automated portfolio advice
- Mobile app
- Complex GraphRAG
- Multi-agent teams
- Full Kubernetes deployment
- Custom financial LLM training
- Full Web SaaS permissions
- Heavy observability stack before audit logs exist

## Development Workflow for Codex

### Subagent Delegation Habit

For every non-trivial request, first ask whether the work can be usefully split across multiple subagents before doing it inline. Prefer parallel subagents when the task has independent slices such as:

- codebase reconnaissance across different packages
- technology or library selection across different options
- schema/design review versus runner/integration review
- implementation review versus test-gap review
- broad research where source families or themes are separable

Keep delegated work concrete and bounded. Use read-only explorer subagents for research, audits, and design comparison. Use worker subagents only when write scopes are disjoint and explicitly assigned. Do not spawn subagents for tiny one-line commands, simple explanations, or tightly coupled edits where coordination would cost more than it saves.

Before editing:

- Inspect the existing repository structure.
- Read this file and any package-level AGENTS.md files.
- Identify the smallest safe change that satisfies the task.
- Avoid broad rewrites unless explicitly requested.

While editing:

- Keep domain logic in backend/core packages, not in notebooks or frontend components.
- Use typed models and explicit schemas.
- Add or update tests with every behavioral change.
- Prefer deterministic functions for ingestion, parsing, validation, event assembly, evidence checks, and ranking.
- Keep LLM prompts versioned and testable.
- Do not commit secrets, API keys, raw credentials, or local `.env` files.

After editing:

- Run the most relevant tests and linters available.
- If a command is missing or fails because the project is not initialized yet, state that clearly in the final summary.
- Summarize changed files, behavior changes, tests run, and remaining risks.

## Expected Commands

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

## Code Style

Python:

- Prefer pure functions for pipeline transforms.
- Use Pydantic models at system boundaries.
- Use timezone-aware datetimes.
- Avoid global mutable state.
- Avoid hidden network calls in constructors or import paths.
- Keep parsing, extraction, retrieval, ranking, and generation modules separate.

TypeScript:

- Use strict TypeScript.
- Keep API types generated or mirrored from backend schemas where possible.
- Keep UI components presentation-focused.

SQL:

- Use migrations for schema changes.
- Keep event, claim, evidence, and provenance tables queryable and auditable.
- Avoid destructive migrations without explicit approval.

## Acceptance Criteria for Early Tasks

A change is acceptable when it:

1. Preserves the Document -> Event -> Claim -> EvidenceSpan model.
2. Keeps source provenance and timestamps intact.
3. Has tests or a clear reason tests are not yet possible.
4. Does not introduce unbounded agent behavior.
5. Does not weaken compliance boundaries around investment advice.
6. Does not add unnecessary infrastructure.
7. Keeps the MVP path simple and reproducible.
8. Keeps external harnesses behind stable tool/result contracts.

## If Uncertain

Prefer the narrower, auditable, reproducible implementation. Ask for clarification before introducing new infrastructure, changing the domain model, or adding external data sources with unclear licensing.
