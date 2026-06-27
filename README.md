# Super Bear

Super Bear is an evidence-first event intelligence prototype for Nasdaq-100 and US technology-stock watchers.

It is not a trading terminal, a buy/sell signal engine, or an investment adviser. The project focuses on collecting source-aware documents and market context, normalizing them into typed records, and preparing the foundation for event, claim, and evidence workflows.

## Current Scope

The first milestone is a bounded source gateway:

- Source Registry for permitted data sources
- adapter skeletons for SEC EDGAR, company IR, YFinance, Tavily, Brave Search, and Stock Sentiment API
- typed schemas for documents, market context, search leads, and weak attention signals
- JSONL outputs for normalized records
- run manifests for auditability

## Design Notes

- Strong evidence sources: SEC EDGAR, company IR, press releases, earnings releases
- Market context sources: YFinance or OpenBB-yfinance
- Search lead sources: Tavily and Brave Search
- Weak signal sources: Stock Sentiment API

Search results and social sentiment are leads or weak signals. They should not be treated as verified factual evidence without independent source-backed confirmation.
