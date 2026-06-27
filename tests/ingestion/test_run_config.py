from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.ingestion.run_config import IngestionRunConfig


def test_ingestion_run_config_loads_yaml_template() -> None:
    config = IngestionRunConfig.from_yaml("configs/ingestion_run.yaml")

    assert config.source_registry_path == Path("configs/sources.yaml")
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


def test_ingestion_run_config_rejects_unsupported_version(tmp_path) -> None:
    config_path = tmp_path / "ingestion_run.yaml"
    config_path.write_text(
        """
version: 2
source_registry_path: configs/sources.yaml
normalized_dir: data/normalized
runs_dir: data/runs
default_limit: null
enabled_source_ids:
  - sec_edgar
skip_unimplemented_adapters: true
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="Input should be 1"):
        IngestionRunConfig.from_yaml(config_path)
