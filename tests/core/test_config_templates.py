from pathlib import Path

import yaml


def test_sources_yaml_registers_first_batch_sources() -> None:
    config = yaml.safe_load(Path("configs/sources.yaml").read_text())

    source_ids = {source["source_id"] for source in config["sources"]}

    assert {
        "sec_edgar",
        "company_ir",
        "yfinance",
        "tavily",
        "brave_search",
        "stock_sentiment",
    }.issubset(source_ids)

    sec = next(source for source in config["sources"] if source["source_id"] == "sec_edgar")
    assert sec["output_kind"] == "document"
    assert sec["source_type"] == "sec_filing"
    assert sec["source_tier"] == "regulatory_primary"
    assert sec["user_agent_env"] == "SEC_USER_AGENT"

    tavily = next(source for source in config["sources"] if source["source_id"] == "tavily")
    assert tavily["output_kind"] == "search_lead"
    assert tavily["api_key_env"] == "TAVILY_API_KEY"


def test_document_rules_yaml_keeps_only_evidence_sources_as_documents() -> None:
    rules = yaml.safe_load(Path("configs/document_rules.yaml").read_text())

    assert "8-K" in rules["sec_edgar"]["include_forms"]
    assert "10-K" in rules["sec_edgar"]["include_forms"]
    assert "EX-99.1" in rules["sec_edgar"]["include_exhibits"]
    assert "company_earnings_release" in rules["company_ir"]["document_source_types"]

    assert sorted(rules["non_document_sources"]) == [
        "brave_search",
        "stock_sentiment",
        "tavily",
        "yfinance",
    ]
