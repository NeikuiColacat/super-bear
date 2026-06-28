# First Batch API Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the remaining first-batch sources from `docs/get_info.md` so each source behaves like SEC EDGAR: fetch, preserve raw data, normalize to typed records, write JSONL, record RunManifest status, and keep provenance intact.

**Architecture:** Keep the existing adapter-based ingestion architecture. Each source adapter returns one primary output kind: `Document`, `MarketContext`, `SearchLead`, or `AttentionSignal`; only `Document` records flow into chunking, claim/evidence extraction, event assembly, and briefing. Search and sentiment records are leads or context until promoted by later deterministic validation.

**Tech Stack:** Python 3.11+, Pydantic, YAML, JSONL, filesystem RawStore, stdlib HTTP/XML/HTML parsing where possible, `yfinance` only for Yahoo market data, pytest, ruff.

---

## 0. Current State

Already implemented:

- `configs/sources.yaml` lists all six first-batch sources.
- `sec_edgar` adapter can fetch SEC submissions and primary filing documents.
- `RawStore`, `JsonlWriter`, `RunManifest`, CLI preview, runner, chunking, candidate extraction stub, ledger, events, event cards, and brief output already exist.
- `OutputKind` already includes `market_context`, `search_lead`, and `attention_signal`.

Current gaps:

- Only `sec_edgar` is registered in `DEFAULT_ADAPTER_CLASSES`.
- No implemented adapters yet for `company_ir`, `yfinance`, `tavily`, `brave_search`, or `stock_sentiment`.
- `packages/core/schemas.py` does not yet define typed Pydantic models for `MarketContext`, `SearchLead`, or `AttentionSignal`.
- `configs/ingestion_run.yaml` has no source-specific options for the remaining sources.
- The runner writes arbitrary adapter dictionaries today, so typed validation for non-Document records should be added before real API use.

Existing uncommitted unrelated files observed before writing this plan:

- `docs/paper.md`
- `tmp/pi_sec_10q_result_text.txt`
- `tmp/sec_edgar_output_preview.html`

Do not modify or revert them while implementing this plan unless the user asks.

## 1. API Research Summary

| Source | What it is | What we should fetch | Output kind | Access requirement | Evidence role |
|---|---|---|---|---|---|
| Company IR / newsroom / earnings releases | Company-controlled pages, RSS, Atom, press-release pages, and earnings release pages. This is not one standard API. | Title, URL, publish time, official body text or metadata, company/ticker identifiers, raw RSS/XML/HTML. | `Document` | No universal key. Needs per-company configured URLs, polite rate limits, and source policy tracking. | Primary company evidence. Enters chunk -> claim -> evidence -> event chain. |
| YFinance | Python package wrapping Yahoo Finance market data endpoints. | Ticker price history, OHLCV rows, actions/dividends/splits, fast quote metadata. | `MarketContext` | No API key, but should cache and rate-limit. Add only `yfinance` dependency, not full OpenBB yet. | Market context only. Never primary evidence for factual claims or causal attribution. |
| Tavily Search API | Search API for web retrieval and optional answer/raw-content enrichment. | Query, result title, URL, snippet/content, score, published date if returned, optional raw content disabled by default. | `SearchLead` | `TAVILY_API_KEY`. Use bounded query budgets. | Lead source only. Search result snippets are not evidence. |
| Brave Search API | Web search API with subscription token auth. | Query, result title, URL, description/snippet, freshness/age if returned, profile/source metadata. | `SearchLead` | `BRAVE_SEARCH_API_KEY` as `X-Subscription-Token`. Use bounded query budgets. | Lead source only. Search result snippets are not evidence. |
| Stock Sentiment API | Social and prediction-market sentiment API family for stocks, described as Reddit / X / Polymarket coverage for US equities in our source list. | Ticker, social source, time window, mention/buzz metrics, sentiment score, optional raw item metadata if license allows. | `AttentionSignal` | `STOCK_SENTIMENT_API_KEY`; endpoint details must be confirmed against the active account docs before implementation. | Weak attention signal only. Cannot confirm a claim without independent evidence. |

Reference links checked for planning:

- Tavily Search API: <https://docs.tavily.com/documentation/api-reference/endpoint/search>
- Brave Web Search API: <https://api-dashboard.search.brave.com/api-reference/web/search/get>
- YFinance documentation: <https://ranaroussi.github.io/yfinance/>
- YFinance `Ticker.history`: <https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html>
- Stock Sentiment API docs entrypoint: <https://api.adanos.org/docs>
- OpenBB docs entrypoint, for later provider consolidation: <https://docs.openbb.co/>

## 2. Recommended Source Order

Implement in this order:

1. `company_ir`: no API key, first-party evidence, same downstream path as SEC.
2. `yfinance`: no API key, gives market context for ranking and event interpretation.
3. `tavily`: key required, bounded search leads for evidence gaps.
4. `brave_search`: key required, second independent search provider.
5. `stock_sentiment`: key required and weaker evidentiary value; integrate last.

This order maximizes usable output while minimizing key/setup blockers.

## 3. Data Contracts

### 3.1 Company IR Produces `Document`

Use the existing `Document` schema. Required normalized fields:

```json
{
  "doc_id": "doc:company_ir:AAPL:<stable-hash>",
  "source_id": "company_ir",
  "source_type": "company_newsroom",
  "source_tier": "company_primary",
  "source_family_id": "issuer_ticker:AAPL",
  "title": "Apple reports third quarter results",
  "url": "https://www.apple.com/newsroom/...",
  "published_at": "2026-07-30T20:30:00Z",
  "retrieved_at": "2026-07-30T20:45:00Z",
  "raw_object_uri": "data/raw/company_ir/AAPL/<hash>.xml",
  "content_hash": "sha256:<64-hex>",
  "parser_version": "company_ir_feed_v1",
  "language": "en",
  "entities": [
    {"kind": "ticker", "value": "AAPL", "identifiers": {"ticker": "AAPL"}}
  ],
  "metadata": {
    "feed_url": "https://www.apple.com/newsroom/rss-feed.rss",
    "entry_id": "...",
    "document_text": "normalized text for chunking"
  }
}
```

Important rule: if a page is not license-clear for full-text retention, store raw metadata/hash/URL and derived excerpt only; do not mirror full article text.

### 3.2 YFinance Produces `MarketContext`

Add a Pydantic model in `packages/core/schemas.py`:

```text
MarketContext
  market_context_id
  source_id
  source_type = market_data
  source_tier = market_context
  source_family_id = provider:yfinance
  ticker
  window_start
  window_end
  retrieved_at
  interval
  currency
  rows
  raw_object_uri
  content_hash
  metadata
```

Each `rows` item should contain only stable normalized market fields:

```text
timestamp
open
high
low
close
volume
dividends
stock_splits
```

Important rule: price movement is context and ranking input, not evidence that something caused the move.

### 3.3 Tavily and Brave Produce `SearchLead`

Add a Pydantic model in `packages/core/schemas.py`:

```text
SearchLead
  search_lead_id
  source_id
  source_type = search
  source_tier = search_lead
  source_family_id = provider:tavily | provider:brave_search
  query
  title
  url
  snippet
  published_at optional
  retrieved_at
  score optional
  rank
  raw_object_uri
  content_hash
  metadata
```

Important rule: search leads can trigger later fetches from primary/independent sources. Search snippets must not become `EvidenceSpan` directly.

### 3.4 Stock Sentiment Produces `AttentionSignal`

Add a Pydantic model in `packages/core/schemas.py`:

```text
AttentionSignal
  attention_signal_id
  source_id
  source_type = social_sentiment
  source_tier = attention_signal
  source_family_id = provider:stock_sentiment
  ticker
  signal_family
  window_start
  window_end
  retrieved_at
  metric_name
  metric_value
  sample_size optional
  raw_object_uri
  content_hash
  metadata
```

Use one record per meaningful metric, for example:

```json
{
  "ticker": "NVDA",
  "signal_family": "reddit",
  "metric_name": "sentiment_score",
  "metric_value": 0.71,
  "sample_size": 128
}
```

Important rule: social sentiment is a weak signal that can affect ranking or trigger investigation, not a factual source of truth.

## 4. Minimal Architecture Additions

Create only these small pieces:

```text
packages/core/schemas.py                 # add MarketContext / SearchLead / AttentionSignal
packages/core/__init__.py                 # export new schemas
packages/ingestion/adapters/http.py       # tiny stdlib HTTP helper: JSON/text fetch, headers, timeout
packages/ingestion/adapters/company_ir.py # RSS/Atom/HTML official-source adapter
packages/ingestion/adapters/yfinance.py   # market context adapter
packages/ingestion/adapters/tavily.py     # Tavily search adapter
packages/ingestion/adapters/brave.py      # Brave search adapter
packages/ingestion/adapters/stock_sentiment.py
packages/ingestion/adapters/__init__.py   # export adapter classes
packages/ingestion/runner.py              # register adapters
configs/ingestion_run.yaml                # add source_options
tests/core/test_context_signal_schemas.py
tests/ingestion/test_company_ir_adapter.py
tests/ingestion/test_yfinance_adapter.py
tests/ingestion/test_search_adapters.py
tests/ingestion/test_stock_sentiment_adapter.py
tests/ingestion/test_runner_first_batch_adapters.py
```

Do not add:

- database tables
- Kafka / Redis
- crawler framework
- browser automation
- full OpenBB dependency
- MCP server
- agent browsing loop

## 5. Detailed Implementation Tasks

### Task 1: Add Typed Schemas for Non-Document Outputs

**Files:**

- Modify: `packages/core/schemas.py`
- Modify: `packages/core/__init__.py`
- Create: `tests/core/test_context_signal_schemas.py`

- [ ] Add `MarketDataRow`, `MarketContext`, `SearchLead`, and `AttentionSignal` Pydantic models.
- [ ] Require timezone-aware timestamps for every timestamp field.
- [ ] Enforce allowed `source_type` / `source_tier` pairs using existing helpers.
- [ ] Enforce `content_hash` format as `sha256:<64-hex>`.
- [ ] Export new models from `packages/core/__init__.py`.
- [ ] Add tests that valid examples pass and invalid tier/type pairs fail.
- [ ] Run:

```bash
uv run pytest tests/core/test_context_signal_schemas.py -q
uv run ruff check packages/core tests/core/test_context_signal_schemas.py
```

Expected result: tests pass and ruff reports no errors.

Commit:

```bash
git add packages/core/schemas.py packages/core/__init__.py tests/core/test_context_signal_schemas.py
git commit -m "feat(core): add typed schemas for market context and source signals"
```

### Task 2: Add a Tiny HTTP Adapter Helper

**Files:**

- Create: `packages/ingestion/adapters/http.py`
- Create: `tests/ingestion/test_http_adapter.py`

Responsibilities:

- Build HTTP requests with source-specific headers.
- Read API keys from environment variables declared in `SourceConfig`.
- Apply explicit timeout.
- Return raw bytes plus response URL/status/content type metadata.
- Convert network failures into `AdapterError` instead of throwing deep urllib errors from adapters.

Minimal API:

```text
fetch_bytes(url, headers, timeout_seconds) -> HttpResponse
fetch_json(url, headers, timeout_seconds) -> tuple[dict, HttpResponse]
post_json(url, headers, payload, timeout_seconds) -> tuple[dict, HttpResponse]
required_env(name) -> str
optional_env(name) -> str | None
```

- [ ] Write tests with monkeypatched `urllib.request.urlopen` so no network is used.
- [ ] Ensure API key values never appear in error messages.
- [ ] Run:

```bash
uv run pytest tests/ingestion/test_http_adapter.py -q
uv run ruff check packages/ingestion/adapters/http.py tests/ingestion/test_http_adapter.py
```

Commit:

```bash
git add packages/ingestion/adapters/http.py tests/ingestion/test_http_adapter.py
git commit -m "feat(ingestion): add minimal HTTP helper for source adapters"
```

### Task 3: Implement Company IR Adapter

**Files:**

- Create: `packages/ingestion/adapters/company_ir.py`
- Create: `tests/ingestion/test_company_ir_adapter.py`
- Modify: `configs/ingestion_run.yaml`
- Modify: `packages/ingestion/adapters/__init__.py`
- Modify: `packages/ingestion/runner.py`

Config shape:

```yaml
source_options:
  company_ir:
    issuers:
      - ticker: AAPL
        company_name: Apple Inc.
        source_family_id: issuer_ticker:AAPL
        feeds:
          - url: https://www.apple.com/newsroom/rss-feed.rss
            source_type: company_newsroom
            parser: rss
```

Adapter behavior:

- Fetch configured RSS/Atom feeds first.
- Convert each feed entry to `Document`.
- Store the raw feed response in RawStore.
- Use stable `doc_id` based on source id, ticker, entry URL, and published timestamp.
- Put normalized body/excerpt in `metadata.document_text` so the existing chunker can process it.
- Respect `limit`.
- Return skipped/failure batch if no issuers are configured.

Tests:

- RSS fixture with two entries becomes two `Document` records.
- Atom fixture with one entry becomes one `Document` record.
- Missing issuer config returns `AdapterError` with code `missing_source_options`.
- Raw XML is written and `raw_object_uri` is non-empty.
- Runner writes `documents.jsonl`, `document_chunks.jsonl` when `write_chunks: true`, and manifest records success.

Run:

```bash
uv run pytest tests/ingestion/test_company_ir_adapter.py tests/ingestion/test_runner_first_batch_adapters.py -q
uv run ruff check packages/ingestion/adapters/company_ir.py tests/ingestion/test_company_ir_adapter.py
```

Commit:

```bash
git add packages/ingestion/adapters/company_ir.py tests/ingestion/test_company_ir_adapter.py tests/ingestion/test_runner_first_batch_adapters.py configs/ingestion_run.yaml packages/ingestion/adapters/__init__.py packages/ingestion/runner.py
git commit -m "feat(ingestion): ingest company IR feeds as primary documents"
```

### Task 4: Implement YFinance Adapter

**Files:**

- Modify: `pyproject.toml`
- Create: `packages/ingestion/adapters/yfinance.py`
- Create: `tests/ingestion/test_yfinance_adapter.py`
- Modify: `configs/ingestion_run.yaml`
- Modify: `packages/ingestion/adapters/__init__.py`
- Modify: `packages/ingestion/runner.py`

Dependency:

```toml
dependencies = [
    "pydantic>=2.8,<3",
    "pyyaml>=6.0,<7",
    "yfinance>=0.2,<0.3",
]
```

Config shape:

```yaml
source_options:
  yfinance:
    tickers:
      - AAPL
      - MSFT
      - NVDA
    period: 5d
    interval: 1d
```

Adapter behavior:

- Use `yfinance.Ticker(ticker).history(period=..., interval=..., actions=True)`.
- Convert each ticker's returned rows into one `MarketContext` record.
- Store raw normalized row payload as JSON in RawStore.
- Keep `source_family_id` as `provider:yfinance`.
- Mark empty history as `failed` with retryable false and code `empty_market_history` for that ticker, or skip the ticker in metadata and succeed if at least one ticker returns rows.

Tests:

- Monkeypatch `yfinance.Ticker` so tests do not call Yahoo.
- Valid fake history becomes a `MarketContext` record.
- Empty history is handled deterministically.
- `MarketContext` rows preserve timestamps and numeric values.
- No market record enters chunk/candidate/event derived outputs.

Run:

```bash
uv sync
uv run pytest tests/ingestion/test_yfinance_adapter.py tests/ingestion/test_runner_first_batch_adapters.py -q
uv run ruff check packages/ingestion/adapters/yfinance.py tests/ingestion/test_yfinance_adapter.py
```

Commit:

```bash
git add pyproject.toml uv.lock packages/ingestion/adapters/yfinance.py tests/ingestion/test_yfinance_adapter.py configs/ingestion_run.yaml packages/ingestion/adapters/__init__.py packages/ingestion/runner.py
git commit -m "feat(ingestion): ingest yfinance market context records"
```

### Task 5: Implement Tavily Search Adapter

**Files:**

- Create: `packages/ingestion/adapters/tavily.py`
- Create or extend: `tests/ingestion/test_search_adapters.py`
- Modify: `configs/ingestion_run.yaml`
- Modify: `packages/ingestion/adapters/__init__.py`
- Modify: `packages/ingestion/runner.py`

Config shape:

```yaml
source_options:
  tavily:
    queries:
      - '"AAPL" earnings release site:apple.com/newsroom'
      - '"MSFT" investor relations earnings release'
    max_results: 5
    search_depth: basic
    include_raw_content: false
```

Adapter behavior:

- Read `TAVILY_API_KEY`.
- POST to Tavily search endpoint.
- Normalize every returned result into `SearchLead`.
- Store full API response JSON in RawStore.
- Include query, rank, title, URL, snippet/content, score, and provider metadata.
- Fail with code `missing_api_key` if the env var is absent.

Tests:

- Missing key returns failure without network.
- Mocked response with two results becomes two `SearchLead` records.
- Raw response is written once per query.
- Snippet fields are normalized consistently even if Tavily returns `content` instead of `description`.
- Runner writes `search_leads.jsonl` and no derived document outputs.

Run:

```bash
uv run pytest tests/ingestion/test_search_adapters.py -q
uv run ruff check packages/ingestion/adapters/tavily.py tests/ingestion/test_search_adapters.py
```

Commit:

```bash
git add packages/ingestion/adapters/tavily.py tests/ingestion/test_search_adapters.py configs/ingestion_run.yaml packages/ingestion/adapters/__init__.py packages/ingestion/runner.py
git commit -m "feat(ingestion): ingest Tavily search results as leads"
```

### Task 6: Implement Brave Search Adapter

**Files:**

- Create: `packages/ingestion/adapters/brave.py`
- Extend: `tests/ingestion/test_search_adapters.py`
- Modify: `configs/ingestion_run.yaml`
- Modify: `packages/ingestion/adapters/__init__.py`
- Modify: `packages/ingestion/runner.py`

Config shape:

```yaml
source_options:
  brave_search:
    queries:
      - '"NVDA" earnings release investor relations'
    count: 5
    freshness: pw
```

Adapter behavior:

- Read `BRAVE_SEARCH_API_KEY`.
- GET Brave Web Search endpoint with `q`, `count`, and optional `freshness`.
- Use `X-Subscription-Token` header.
- Normalize web results into `SearchLead`.
- Store full API response JSON in RawStore.
- Preserve result rank and provider-specific metadata.

Tests:

- Missing key returns failure without network.
- Mocked Brave response with `web.results` becomes `SearchLead` records.
- Missing `web.results` returns success with zero records and a manifest output of zero written, or failure with `empty_search_results`; choose one behavior and keep it consistent with Tavily.

Run:

```bash
uv run pytest tests/ingestion/test_search_adapters.py -q
uv run ruff check packages/ingestion/adapters/brave.py tests/ingestion/test_search_adapters.py
```

Commit:

```bash
git add packages/ingestion/adapters/brave.py tests/ingestion/test_search_adapters.py configs/ingestion_run.yaml packages/ingestion/adapters/__init__.py packages/ingestion/runner.py
git commit -m "feat(ingestion): ingest Brave search results as leads"
```

### Task 7: Implement Stock Sentiment Adapter

**Files:**

- Create: `packages/ingestion/adapters/stock_sentiment.py`
- Create: `tests/ingestion/test_stock_sentiment_adapter.py`
- Modify: `configs/ingestion_run.yaml`
- Modify: `packages/ingestion/adapters/__init__.py`
- Modify: `packages/ingestion/runner.py`

Config shape:

```yaml
source_options:
  stock_sentiment:
    tickers:
      - AAPL
      - MSFT
      - NVDA
    sources:
      - reddit
      - x
      - polymarket
    lookback: 24h
```

Adapter behavior:

- Read `STOCK_SENTIMENT_API_KEY`.
- Fetch per ticker/source/window according to the active Adanos API docs.
- Normalize each metric into `AttentionSignal`.
- Store full response JSON in RawStore.
- If the provider returns raw social posts, keep only allowed metadata unless source license permits full text.
- Treat unsupported tickers or sources as skipped metrics recorded in adapter metadata.

Tests:

- Missing key returns failure without network.
- Mocked Reddit metric response becomes one or more `AttentionSignal` records.
- Mocked X or Polymarket response maps to the same normalized schema.
- Raw social text is not required in normalized records.
- Runner writes `attention_signals.jsonl` and no derived document outputs.

Run:

```bash
uv run pytest tests/ingestion/test_stock_sentiment_adapter.py -q
uv run ruff check packages/ingestion/adapters/stock_sentiment.py tests/ingestion/test_stock_sentiment_adapter.py
```

Commit:

```bash
git add packages/ingestion/adapters/stock_sentiment.py tests/ingestion/test_stock_sentiment_adapter.py configs/ingestion_run.yaml packages/ingestion/adapters/__init__.py packages/ingestion/runner.py
git commit -m "feat(ingestion): ingest stock sentiment as attention signals"
```

### Task 8: Add First-Batch Run Presets

**Files:**

- Create: `configs/ingestion_first_batch.sample.yaml`
- Modify: `docs/get_info.md`
- Optional: `README.md`

Create a safe sample config that:

- Runs `company_ir` and `yfinance` without API keys.
- Keeps Tavily, Brave, and Stock Sentiment source options present but documented as requiring env vars.
- Uses small limits.
- Does not enable `write_brief` by default.

Suggested smoke commands:

```bash
uv run python -m packages.ingestion.runner --config configs/ingestion_first_batch.sample.yaml --source company_ir --limit 2
uv run python -m packages.ingestion.runner --config configs/ingestion_first_batch.sample.yaml --source yfinance --limit 2
TAVILY_API_KEY=... uv run python -m packages.ingestion.runner --config configs/ingestion_first_batch.sample.yaml --source tavily --limit 2
BRAVE_SEARCH_API_KEY=... uv run python -m packages.ingestion.runner --config configs/ingestion_first_batch.sample.yaml --source brave_search --limit 2
STOCK_SENTIMENT_API_KEY=... uv run python -m packages.ingestion.runner --config configs/ingestion_first_batch.sample.yaml --source stock_sentiment --limit 2
```

Run:

```bash
uv run pytest tests/ingestion -q
uv run ruff check .
uv run ruff format --check .
```

Commit:

```bash
git add configs/ingestion_first_batch.sample.yaml docs/get_info.md README.md
git commit -m "docs(ingestion): document first-batch source run presets"
```

### Task 9: Real API Smoke Runs

Run these after the adapter tests pass. Do not commit `.env` files or raw keys.

No-key smoke:

```bash
uv run python -m packages.ingestion.runner --source company_ir --limit 2
uv run python -m packages.ingestion.runner --source yfinance --limit 2
```

Keyed smoke:

```bash
uv run python -m packages.ingestion.runner --source tavily --limit 2
uv run python -m packages.ingestion.runner --source brave_search --limit 2
uv run python -m packages.ingestion.runner --source stock_sentiment --limit 2
```

Validate outputs:

```bash
ls -lh data/normalized data/runs
head -n 1 data/normalized/documents.jsonl
head -n 1 data/normalized/market_context.jsonl
head -n 1 data/normalized/search_leads.jsonl
head -n 1 data/normalized/attention_signals.jsonl
```

Expected behavior:

- `company_ir` writes `documents.jsonl`.
- `yfinance` writes `market_context.jsonl`.
- Tavily and Brave write `search_leads.jsonl`.
- Stock Sentiment writes `attention_signals.jsonl`.
- RunManifest records success, failed, or skipped for every requested source.
- Missing API keys produce clear failed/skipped results without crashing the whole run.

Commit only code and docs, not fetched raw data:

```bash
git status --short
git add <code-and-doc-files-only>
git commit -m "test(ingestion): verify first-batch API smoke runs"
```

## 6. Acceptance Criteria

The integration is complete when:

1. All five remaining adapters are implemented and registered.
2. Each adapter writes raw payloads and normalized JSONL.
3. Each source appears correctly in RunManifest with status, written count, raw URIs, output path, and error/skipped reason.
4. `Document` sources flow through chunking and downstream derived outputs.
5. `MarketContext`, `SearchLead`, and `AttentionSignal` do not flow into evidence ledger automatically.
6. Missing API keys never crash the whole pipeline.
7. API keys never appear in logs, manifest errors, or test snapshots.
8. Unit tests run without live network.
9. Real smoke tests can be run one source at a time.
10. No user-facing factual statement is generated from search snippets or social sentiment alone.

## 7. Key Decisions

Use `yfinance` first, not OpenBB:

- It is smaller and matches the current MVP dependency style.
- It avoids pulling a broad financial platform before the market context contract is proven.
- OpenBB can still be added later as a second market adapter if provider consolidation becomes valuable.

Use stdlib HTTP first:

- Current dependencies are intentionally minimal.
- We only need simple GET/POST JSON and text fetches.
- Add `httpx` later only if retries, sessions, proxies, async, or richer timeout control become necessary.

Keep search and sentiment out of the ledger by default:

- Search APIs return leads, not authoritative sources.
- Social sentiment is noisy and often licensing-sensitive.
- The ledger should remain evidence-first and source-aware.

Implement Stock Sentiment last:

- It is weakest as evidence.
- It is most likely to have account-specific docs and licensing constraints.
- The rest of the pipeline can already prove useful before this is wired.

## 8. Execution Recommendation

If doing this in one pass, execute Tasks 1-4 first and run tests. That gives us:

- Company first-party documents.
- Market context.
- Typed non-document outputs.
- A clean pattern for the keyed adapters.

Then execute Tasks 5-7 for the API-key sources. Finish with Task 8 docs and Task 9 live smoke runs.

The smallest useful milestone is:

```text
Task 1 + Task 3 + Task 4
```

That milestone gives us official company documents plus price context without needing new API keys.
