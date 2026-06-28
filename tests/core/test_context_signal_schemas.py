from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from packages.core import (
    AttentionSignal,
    MarketContext,
    MarketDataRow,
    SearchLead,
    SourceTier,
    SourceType,
    make_content_hash,
)


def _now() -> datetime:
    return datetime(2026, 6, 29, 9, 30, tzinfo=timezone.utc)


def test_market_context_records_price_rows_as_context_only() -> None:
    context = MarketContext(
        market_context_id="market:yfinance:aapl:20260629",
        source_id="yfinance",
        source_type=SourceType.MARKET_DATA,
        source_tier=SourceTier.MARKET_CONTEXT,
        source_family_id="provider:yfinance",
        ticker="AAPL",
        window_start=datetime(2026, 6, 28, tzinfo=timezone.utc),
        window_end=_now(),
        retrieved_at=_now(),
        interval="1d",
        currency="USD",
        rows=(
            MarketDataRow(
                timestamp=datetime(2026, 6, 28, tzinfo=timezone.utc),
                open=100.0,
                high=103.0,
                low=99.0,
                close=102.0,
                volume=123456,
                dividends=0.0,
                stock_splits=0.0,
            ),
        ),
        raw_object_uri="data/raw/yfinance/aapl.json",
        content_hash=make_content_hash("aapl market rows"),
    )

    assert context.source_type is SourceType.MARKET_DATA
    assert context.source_tier is SourceTier.MARKET_CONTEXT
    assert context.rows[0].close == 102.0


def test_search_lead_records_query_result_but_is_not_document_evidence() -> None:
    lead = SearchLead(
        search_lead_id="search:tavily:aapl:000000",
        source_id="tavily",
        source_type=SourceType.SEARCH,
        source_tier=SourceTier.SEARCH_LEAD,
        source_family_id="provider:tavily",
        query='"AAPL" earnings release',
        title="Apple reports results",
        url="https://www.apple.com/newsroom/example/",
        snippet="Apple announced quarterly results.",
        published_at=_now(),
        retrieved_at=_now(),
        score=0.91,
        rank=1,
        raw_object_uri="data/raw/tavily/aapl.json",
        content_hash=make_content_hash("tavily result"),
    )

    assert lead.source_type is SourceType.SEARCH
    assert lead.rank == 1


def test_attention_signal_records_social_metric_as_weak_signal() -> None:
    signal = AttentionSignal(
        attention_signal_id="attention:stock_sentiment:nvda:reddit:mentions",
        source_id="stock_sentiment",
        source_type=SourceType.SOCIAL_SENTIMENT,
        source_tier=SourceTier.ATTENTION_SIGNAL,
        source_family_id="provider:stock_sentiment",
        ticker="NVDA",
        signal_family="reddit",
        window_start=datetime(2026, 6, 28, tzinfo=timezone.utc),
        window_end=_now(),
        retrieved_at=_now(),
        metric_name="mentions",
        metric_value=128.0,
        sample_size=128,
        raw_object_uri="data/raw/stock_sentiment/nvda.json",
        content_hash=make_content_hash("reddit nvda mentions"),
    )

    assert signal.signal_family == "reddit"
    assert signal.metric_value == 128.0


def test_context_signal_models_reject_bad_type_tier_pairs() -> None:
    with pytest.raises(ValidationError, match="not valid for source_type"):
        SearchLead(
            search_lead_id="search:tavily:aapl:000000",
            source_id="tavily",
            source_type=SourceType.SEARCH,
            source_tier=SourceTier.MARKET_CONTEXT,
            source_family_id="provider:tavily",
            query="AAPL",
            title="Apple",
            url="https://example.com/apple",
            snippet="Apple",
            retrieved_at=_now(),
            rank=1,
            raw_object_uri="data/raw/tavily/aapl.json",
            content_hash=make_content_hash("bad pair"),
        )


def test_context_signal_models_require_timezone_aware_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        MarketDataRow(
            timestamp=datetime(2026, 6, 29),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1,
        )
