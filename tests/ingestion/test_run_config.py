from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.ingestion.run_config import IngestionRunConfig


def test_ingestion_run_config_loads_yaml_template() -> None:
    config = IngestionRunConfig.from_yaml("configs/ingestion_run.yaml")

    assert config.source_registry_path == Path("configs/sources.yaml")
    assert config.raw_dir == Path("data/raw")
    assert config.normalized_dir == Path("data/normalized")
    assert config.runs_dir == Path("data/runs")
    assert config.default_limit is None
    assert config.enabled_source_ids == (
        "sec_edgar",
        "company_ir",
        "yfinance",
        "tavily",
        "brave_search",
        "stock_sentiment",
    )
    assert config.skip_unimplemented_adapters is True
    assert config.write_ledger is False
    assert config.write_events is False
    assert config.write_event_cards is False
    assert config.write_brief is False
    assert config.source_options["sec_edgar"]["ciks"] == ["0000320193"]
    assert config.source_options["sec_edgar"]["fetch_primary_documents"] is True
    assert config.source_options["sec_edgar"]["primary_document_limit"] == 1
    assert config.source_options["sec_edgar"]["text_excerpt_chars"] == 500
    assert (
        config.source_options["company_ir"]["catalog_path"]
        == "configs/company_ir_sources.yaml"
    )
    assert config.source_options["yfinance"]["tickers"] == ["AAPL"]
    assert config.source_options["tavily"]["queries"]
    assert config.source_options["brave_search"]["queries"]
    assert config.source_options["stock_sentiment"]["tickers"] == ["AAPL"]


def test_nasdaq100_company_ir_sample_config_loads_catalog_path() -> None:
    config = IngestionRunConfig.from_yaml(
        "configs/ingestion_nasdaq100_company_ir.sample.yaml"
    )

    assert config.enabled_source_ids == ("company_ir",)
    assert config.write_chunks is True
    assert (
        config.source_options["company_ir"]["catalog_path"]
        == "configs/company_ir_sources.yaml"
    )
    assert config.source_options["company_ir"]["continue_on_feed_error"] is True
    assert config.source_options["company_ir"]["published_after"] == (
        "2026-06-29T00:00:00Z"
    )


def test_ingestion_run_config_rejects_unsupported_version(tmp_path) -> None:
    config_path = tmp_path / "ingestion_run.yaml"
    config_path.write_text(
        """
version: 2
source_registry_path: configs/sources.yaml
raw_dir: data/raw
normalized_dir: data/normalized
runs_dir: data/runs
default_limit: null
enabled_source_ids:
  - sec_edgar
skip_unimplemented_adapters: true
source_options:
  sec_edgar:
    ciks:
      - "0000320193"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="Input should be 1"):
        IngestionRunConfig.from_yaml(config_path)


def test_ingestion_run_config_can_enable_pre_event_ledger(tmp_path) -> None:
    config_path = tmp_path / "ingestion_run.yaml"
    config_path.write_text(
        """
version: 1
source_registry_path: configs/sources.yaml
raw_dir: data/raw
normalized_dir: data/normalized
runs_dir: data/runs
enabled_source_ids:
  - sec_edgar
write_ledger: true
source_options:
  sec_edgar:
    ciks:
      - "0000320193"
""",
        encoding="utf-8",
    )

    config = IngestionRunConfig.from_yaml(config_path)

    assert config.write_ledger is True


def test_ingestion_run_config_can_enable_events(tmp_path) -> None:
    config_path = tmp_path / "ingestion_run.yaml"
    config_path.write_text(
        """
version: 1
source_registry_path: configs/sources.yaml
raw_dir: data/raw
normalized_dir: data/normalized
runs_dir: data/runs
enabled_source_ids:
  - sec_edgar
write_events: true
source_options:
  sec_edgar:
    ciks:
      - "0000320193"
""",
        encoding="utf-8",
    )

    config = IngestionRunConfig.from_yaml(config_path)

    assert config.write_events is True


def test_ingestion_run_config_can_enable_event_cards_and_brief(tmp_path) -> None:
    config_path = tmp_path / "ingestion_run.yaml"
    config_path.write_text(
        """
version: 1
source_registry_path: configs/sources.yaml
raw_dir: data/raw
normalized_dir: data/normalized
runs_dir: data/runs
enabled_source_ids:
  - sec_edgar
write_event_cards: true
write_brief: true
source_options:
  sec_edgar:
    ciks:
      - "0000320193"
""",
        encoding="utf-8",
    )

    config = IngestionRunConfig.from_yaml(config_path)

    assert config.write_event_cards is True
    assert config.write_brief is True
