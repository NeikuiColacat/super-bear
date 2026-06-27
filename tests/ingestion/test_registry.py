from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.core import OutputKind, SourceTier, SourceType
from packages.ingestion.registry import SourceRegistry


def test_registry_loads_first_batch_sources_from_yaml() -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    assert registry.source_ids == (
        "sec_edgar",
        "company_ir",
        "yfinance",
        "tavily",
        "brave_search",
        "stock_sentiment",
    )

    sec = registry.get("sec_edgar")
    assert sec.output_kind is OutputKind.DOCUMENT
    assert sec.default_source_type is SourceType.SEC_FILING
    assert sec.allowed_source_types == (
        SourceType.SEC_FILING,
        SourceType.SEC_EXHIBIT,
    )
    assert sec.source_tier is SourceTier.REGULATORY_PRIMARY
    assert sec.user_agent_env == "SEC_USER_AGENT"
    assert sec.requires_api_key is False

    company_ir = registry.get("company_ir")
    assert company_ir.default_source_type is SourceType.COMPANY_IR
    assert company_ir.allowed_source_types == (
        SourceType.COMPANY_IR,
        SourceType.COMPANY_NEWSROOM,
        SourceType.COMPANY_EARNINGS_RELEASE,
    )

    tavily = registry.get("tavily")
    assert tavily.output_kind is OutputKind.SEARCH_LEAD
    assert tavily.api_key_env == "TAVILY_API_KEY"
    assert tavily.requires_api_key is True


def test_registry_filters_enabled_sources_by_output_kind() -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    assert [source.source_id for source in registry.enabled_sources()] == [
        "sec_edgar",
        "company_ir",
        "yfinance",
        "tavily",
        "brave_search",
        "stock_sentiment",
    ]
    assert [source.source_id for source in registry.enabled_sources(OutputKind.DOCUMENT)] == [
        "sec_edgar",
        "company_ir",
    ]
    assert [
        source.source_id for source in registry.enabled_sources(OutputKind.SEARCH_LEAD)
    ] == [
        "tavily",
        "brave_search",
    ]


def test_registry_missing_source_id_raises_key_error() -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    with pytest.raises(KeyError, match="unknown_source"):
        registry.get("unknown_source")


def test_registry_rejects_duplicate_source_ids(tmp_path: Path) -> None:
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        """
version: 1
sources:
  - source_id: sec_edgar
    enabled: true
    adapter: sec_edgar
    output_kind: document
    default_source_type: sec_filing
    allowed_source_types:
      - sec_filing
    source_tier: regulatory_primary
    source_family_strategy: issuer
    requires_api_key: false
    rate_limit_per_second: 8
    license_notes: first
  - source_id: sec_edgar
    enabled: true
    adapter: sec_edgar_copy
    output_kind: document
    default_source_type: sec_filing
    allowed_source_types:
      - sec_filing
    source_tier: regulatory_primary
    source_family_strategy: issuer
    requires_api_key: false
    rate_limit_per_second: 8
    license_notes: duplicate
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate source_id"):
        SourceRegistry.from_yaml(config_path)


def test_registry_rejects_inconsistent_output_mapping(tmp_path: Path) -> None:
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        """
version: 1
sources:
  - source_id: broken_tavily
    enabled: true
    adapter: tavily_search
    output_kind: search_lead
    default_source_type: sec_filing
    source_tier: search_lead
    source_family_strategy: provider
    api_key_env: TAVILY_API_KEY
    requires_api_key: true
    rate_limit_per_second: 1
    license_notes: invalid
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="search_lead sources must use search"):
        SourceRegistry.from_yaml(config_path)


def test_registry_rejects_document_source_types_that_do_not_match_tier(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        """
version: 1
sources:
  - source_id: bad_sec
    enabled: true
    adapter: sec_edgar
    output_kind: document
    default_source_type: sec_filing
    allowed_source_types:
      - sec_filing
    source_tier: company_distributed
    source_family_strategy: issuer
    requires_api_key: false
    rate_limit_per_second: 8
    license_notes: invalid
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="not valid for source_type"):
        SourceRegistry.from_yaml(config_path)
