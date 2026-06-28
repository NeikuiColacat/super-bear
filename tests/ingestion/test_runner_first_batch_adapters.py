from packages.ingestion.runner import DEFAULT_ADAPTER_CLASSES


def test_default_adapter_registry_uses_source_id_keys() -> None:
    expected = {
        "sec_edgar",
        "company_ir",
        "yfinance",
        "tavily",
        "brave_search",
        "stock_sentiment",
    }

    assert set(DEFAULT_ADAPTER_CLASSES) == expected
    for source_id, adapter_class in DEFAULT_ADAPTER_CLASSES.items():
        assert adapter_class.source_id == source_id
