from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

from pydantic import BaseModel, ConfigDict, Field
import yaml


class CompanyIrCatalogAudit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_path: str
    universe: str | None = None
    as_of: str | None = None
    issuer_count: int = Field(ge=0)
    unique_ticker_count: int = Field(ge=0)
    issuer_with_feed_count: int = Field(ge=0)
    feed_count: int = Field(ge=0)
    source_type_counts: dict[str, int]
    missing_cik_tickers: tuple[str, ...]
    missing_feed_tickers: tuple[str, ...]
    duplicate_tickers: tuple[str, ...]


def audit_company_ir_catalog(path: str | Path) -> CompanyIrCatalogAudit:
    catalog_path = Path(path)
    raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Company IR catalog must contain a mapping")
    if raw.get("version") != 1:
        raise ValueError("Company IR catalog must use version: 1")

    issuers = raw.get("issuers", [])
    if not isinstance(issuers, list):
        raise ValueError("Company IR catalog must contain an issuers list")

    tickers: list[str] = []
    source_type_counts: Counter[str] = Counter()
    missing_cik_tickers: set[str] = set()
    missing_feed_tickers: set[str] = set()
    feed_count = 0
    issuer_with_feed_count = 0

    for issuer in issuers:
        if not isinstance(issuer, dict):
            raise ValueError("Company IR catalog issuers must be mappings")
        ticker = str(issuer.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        tickers.append(ticker)

        source_family_id = str(issuer.get("source_family_id", "")).strip()
        if not source_family_id.startswith("issuer:"):
            missing_cik_tickers.add(ticker)

        feeds = issuer.get("feeds", [])
        if not isinstance(feeds, list):
            raise ValueError(f"Company IR catalog feeds must be a list for {ticker}")
        if not feeds:
            missing_feed_tickers.add(ticker)
            continue

        issuer_with_feed_count += 1
        feed_count += len(feeds)
        for feed in feeds:
            if not isinstance(feed, dict):
                raise ValueError(
                    f"Company IR catalog feed must be a mapping for {ticker}"
                )
            source_type = str(feed.get("source_type", "company_newsroom"))
            source_type_counts[source_type] += 1

    ticker_counts = Counter(tickers)
    duplicate_tickers = tuple(
        sorted(ticker for ticker, count in ticker_counts.items() if count > 1)
    )

    return CompanyIrCatalogAudit(
        catalog_path=str(catalog_path),
        universe=raw.get("universe"),
        as_of=raw.get("as_of"),
        issuer_count=len(issuers),
        unique_ticker_count=len(ticker_counts),
        issuer_with_feed_count=issuer_with_feed_count,
        feed_count=feed_count,
        source_type_counts=dict(sorted(source_type_counts.items())),
        missing_cik_tickers=tuple(sorted(missing_cik_tickers)),
        missing_feed_tickers=tuple(sorted(missing_feed_tickers)),
        duplicate_tickers=duplicate_tickers,
    )


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    path = args[0] if args else "configs/company_ir_sources.yaml"
    audit = audit_company_ir_catalog(path)
    print(
        json.dumps(
            audit.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
