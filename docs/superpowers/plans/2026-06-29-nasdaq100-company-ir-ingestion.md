# Nasdaq-100 Company IR Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scale `company_ir` from one issuer to a maintainable Nasdaq-100 company IR / press release / earnings release ingestion path.

**Architecture:** Keep one `company_ir` adapter and move issuer/feed coverage into a versioned YAML catalog. Prefer official RSS/Atom feeds; tolerate per-feed failures; filter by daily publish window; use paid search APIs only for missing feeds, evidence gaps, or high-priority events.

**Tech Stack:** Existing Python ingestion runner, Pydantic, YAML, stdlib XML parsing, filesystem RawStore, JSONL, pytest, ruff.

---

## 1. Technical Choice

Use a static audited catalog:

```text
configs/company_ir_sources.yaml
```

Do not create 100 separate source IDs. Do not add a database, crawler framework, browser automation, or MCP surface for this layer.

Why:

- Nasdaq-100 membership changes, so the constituent snapshot needs an `as_of` date.
- Company IR feeds are heterogeneous; a reviewed catalog is safer than dynamic discovery on every run.
- The current `CompanyIrAdapter` already supports many issuers and many feeds.
- RSS/Atom is enough for the first production-shaped pass.

Reference sources for discovery:

- Nasdaq-100 official page: <https://www.nasdaq.com/solutions/global-indexes/nasdaq-100>
- SEC ticker-to-CIK data: <https://www.sec.gov/files/company_tickers.json>
- Invesco QQQ holdings as cross-check only: <https://www.invesco.com/qqq-etf/en/about.html>

## 2. Runtime Shape

Daily source-first run:

```text
SEC EDGAR
Company IR RSS/Atom
YFinance market context
```

Conditional paid enrichment:

```text
Tavily / Brave only for feed gaps, important events, conflicts, or top movers
Stock Sentiment only for top-N attention checks
```

Company IR daily command:

```bash
uv run python -m packages.ingestion.runner \
  --config configs/ingestion_nasdaq100_company_ir.sample.yaml \
  --source company_ir \
  --write-chunks
```

## 3. Catalog Shape

```yaml
version: 1
universe: nasdaq100
as_of: "2026-06-29"
universe_source_url: https://www.nasdaq.com/solutions/global-indexes/nasdaq-100/companies
issuers:
  - ticker: AAPL
    company_name: Apple Inc.
    source_family_id: issuer:0000320193
    ir_home_url: https://www.apple.com/investor-relations/
    provider_hint: first_party
    feeds:
      - url: https://www.apple.com/newsroom/rss-feed.rss
        source_type: company_newsroom
        official: true
    html_sources: []
    sec_fallback:
      forms: ["8-K", "10-Q", "10-K"]
      exhibit_types: ["EX-99.1"]
```

Use `issuer:<CIK>` when known. Fall back to `issuer_ticker:<TICKER>` only until CIK mapping is confirmed.

## 4. Required Adapter Behavior

- Load `catalog_path` from `source_options.company_ir`.
- Keep inline `issuers` support for tests and one-off runs.
- Filter daily items with `published_after`.
- Continue after one feed fails; fail only when all feeds fail and no records are produced.
- Sleep between feed requests using `source.rate_limit_per_second`.
- Preserve raw XML, `content_hash`, `raw_object_uri`, `retrieved_at`, `published_at`, `source_tier`, and `source_family_id`.
- Persist partial feed warnings into `RunManifest`.

## 5. Fallback Order

1. Official issuer RSS/Atom feed.
2. Official issuer HTML list pages, only for common verified provider patterns.
3. SEC submissions and 8-K / 6-K / EX-99.1 exhibits for earnings releases.
4. Press wires as `company_distributed`, not independent confirmation.
5. Tavily/Brave only to discover missing official URLs or fill evidence gaps.

Do not add a headless browser or generic crawler until RSS/Atom plus a small
number of official HTML patterns fail to cover the daily use case.

## 6. Rollout Plan

### Task 1: Adapter Scale Hooks

- [x] Add `catalog_path`.
- [x] Add `published_after`.
- [x] Add per-feed failure tolerance.
- [x] Add feed request rate-limit hook.
- [x] Persist partial feed warnings in RunManifest.
- [x] Add tests for each behavior.

### Task 2: Seed Catalog

- [x] Add `configs/company_ir_sources.yaml`.
- [x] Move AAPL into the catalog.
- [x] Add `configs/ingestion_nasdaq100_company_ir.sample.yaml`.

### Task 3: Catalog Expansion

- [x] Freeze Nasdaq-100 constituent snapshot with `as_of`.
- [x] Map each ticker to CIK using SEC `company_tickers.json`.
- [ ] Add official RSS/Atom feeds where verified.
- [x] Mark unresolved issuers with `feeds: []` until verified.

Verified feed batches:

- 2026-06-30: added MSFT, NVDA, AMZN, META, GOOGL, AVGO, AMD, and NFLX.

### Task 4: Coverage Audit

- [x] Add a lightweight report that counts issuers, feeds, source types, and missing CIKs.
- [x] Run `company_ir` with `--limit 10`.
- [ ] Run full `company_ir` after at least 50 verified feeds.

## 7. Acceptance Criteria

Current implementation milestone is acceptable when:

1. Company IR can load issuers from a catalog.
2. Existing AAPL smoke still works through the catalog.
3. Daily filtering can exclude old feed items.
4. One failing feed does not fail the whole run.
5. Tests and lint pass.

Full Nasdaq-100 completion requires a separately reviewed catalog with current constituents and verified official feed URLs.
