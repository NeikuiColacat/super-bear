import json

from packages.ingestion.catalog_audit import audit_company_ir_catalog, main


def test_company_ir_catalog_audit_counts_coverage(tmp_path) -> None:
    catalog_path = tmp_path / "company_ir_sources.yaml"
    catalog_path.write_text(
        """
version: 1
universe: nasdaq100
as_of: "2026-06-29"
issuers:
  - ticker: AAPL
    company_name: Apple Inc.
    source_family_id: issuer:0000320193
    feeds:
      - url: https://www.apple.com/newsroom/rss-feed.rss
        source_type: company_newsroom
  - ticker: MSFT
    company_name: Microsoft Corporation
    feeds: []
  - ticker: MSFT
    company_name: Microsoft Corporation duplicate
    source_family_id: issuer:0000789019
    feeds:
      - url: https://example.com/msft.xml
        source_type: company_ir
""",
        encoding="utf-8",
    )

    audit = audit_company_ir_catalog(catalog_path)

    assert audit.issuer_count == 3
    assert audit.unique_ticker_count == 2
    assert audit.feed_count == 2
    assert audit.issuer_with_feed_count == 2
    assert audit.source_type_counts == {
        "company_ir": 1,
        "company_newsroom": 1,
    }
    assert audit.missing_cik_tickers == ("MSFT",)
    assert audit.missing_feed_tickers == ("MSFT",)
    assert audit.duplicate_tickers == ("MSFT",)


def test_company_ir_catalog_audit_cli_prints_json(tmp_path, capsys) -> None:
    catalog_path = tmp_path / "company_ir_sources.yaml"
    catalog_path.write_text(
        """
version: 1
universe: nasdaq100
as_of: "2026-06-29"
issuers: []
""",
        encoding="utf-8",
    )

    exit_code = main([str(catalog_path)])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["universe"] == "nasdaq100"
    assert payload["issuer_count"] == 0


def test_repo_company_ir_catalog_has_nasdaq100_seed_skeleton() -> None:
    audit = audit_company_ir_catalog("configs/company_ir_sources.yaml")

    assert audit.universe == "nasdaq100"
    assert audit.issuer_count == 101
    assert audit.unique_ticker_count == 101
    assert audit.feed_count == 1
    assert audit.missing_cik_tickers == ()
    assert audit.duplicate_tickers == ()
    assert len(audit.missing_feed_tickers) == 100
