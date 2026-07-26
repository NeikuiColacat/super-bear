import json
from urllib.parse import parse_qs, urlparse

from packages.core import OutputKind, SourceTier, SourceType
from packages.ingestion.adapters.brave import BraveSearchAdapter
from packages.ingestion.adapters.tavily import TavilySearchAdapter
from packages.ingestion.registry import SourceRegistry
from packages.ingestion.runner import run_ingestion


def _registry() -> SourceRegistry:
    return SourceRegistry.from_yaml("configs/sources.yaml")


def test_tavily_adapter_requires_api_key_before_network(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    adapter = TavilySearchAdapter(
        _registry().get("tavily"),
        raw_dir=tmp_path / "raw",
        options={"queries": ["AAPL earnings"]},
        post_json=lambda url, headers, payload, timeout: (_ for _ in ()).throw(
            AssertionError("network should not run")
        ),
    )

    batch = adapter.fetch()

    assert batch.ok is False
    assert batch.error is not None
    assert batch.error.code == "missing_api_key"


def test_tavily_adapter_maps_results_to_search_leads(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "secret")

    def fake_post(
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout: float,
    ) -> dict[str, object]:
        assert url == "https://api.tavily.com/search"
        assert headers["Authorization"] == "Bearer secret"
        assert payload["query"] == "AAPL earnings"
        return {
            "results": [
                {
                    "title": "Apple results",
                    "url": "https://www.apple.com/newsroom/results/",
                    "content": "Apple announced quarterly results.",
                    "score": 0.93,
                    "published_date": "2026-06-29T13:00:00Z",
                }
            ]
        }

    adapter = TavilySearchAdapter(
        _registry().get("tavily"),
        raw_dir=tmp_path / "raw",
        options={"queries": ["AAPL earnings"], "max_results": 1},
        post_json=fake_post,
    )

    batch = adapter.fetch()

    assert batch.ok is True
    assert batch.output_kind is OutputKind.SEARCH_LEAD
    assert len(batch.records) == 1
    record = batch.records[0]
    assert record["source_type"] == SourceType.SEARCH
    assert record["source_tier"] == SourceTier.SEARCH_LEAD
    assert record["source_family_id"] == "provider:tavily"
    assert record["snippet"] == "Apple announced quarterly results."
    assert batch.raw_uris[0].endswith(".json")


def test_tavily_adapter_passes_domain_filters(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "secret")

    def fake_post(
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout: float,
    ) -> dict[str, object]:
        assert payload["include_domains"] == ["apple.com", "sec.gov"]
        assert payload["exclude_domains"] == ["example.com"]
        return {"results": []}

    adapter = TavilySearchAdapter(
        _registry().get("tavily"),
        raw_dir=tmp_path / "raw",
        options={
            "queries": ["AAPL official earnings"],
            "include_domains": ["apple.com", "sec.gov"],
            "exclude_domains": ["example.com"],
        },
        post_json=fake_post,
    )

    batch = adapter.fetch()

    assert batch.ok is True


def test_tavily_adapter_enforces_domain_filters_locally(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "secret")

    def fake_post(
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout: float,
    ) -> dict[str, object]:
        return {
            "results": [
                {
                    "title": "Apple Nasdaq quote",
                    "url": "https://www.nasdaq.com/market-activity/stocks/aapl",
                    "content": "Apple stock quote page.",
                },
                {
                    "title": "Apple Newsroom",
                    "url": "https://www.apple.com/newsroom/",
                    "content": "Apple official newsroom.",
                },
            ]
        }

    adapter = TavilySearchAdapter(
        _registry().get("tavily"),
        raw_dir=tmp_path / "raw",
        options={
            "queries": ["AAPL official news"],
            "include_domains": ["apple.com"],
        },
        post_json=fake_post,
    )

    batch = adapter.fetch()

    assert batch.ok is True
    assert [record["url"] for record in batch.records] == [
        "https://www.apple.com/newsroom/"
    ]


def test_brave_adapter_requires_api_key_before_network(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    adapter = BraveSearchAdapter(
        _registry().get("brave_search"),
        raw_dir=tmp_path / "raw",
        options={"queries": ["NVDA earnings"]},
        fetch_json=lambda url, headers, timeout: (_ for _ in ()).throw(
            AssertionError("network should not run")
        ),
    )

    batch = adapter.fetch()

    assert batch.ok is False
    assert batch.error is not None
    assert batch.error.code == "missing_api_key"


def test_brave_adapter_maps_results_to_search_leads(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "secret")

    def fake_fetch(
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        assert url.startswith("https://api.search.brave.com/res/v1/web/search?")
        params = parse_qs(urlparse(url).query)
        assert params["text_decorations"] == ["false"]
        assert headers["X-Subscription-Token"] == "secret"
        return {
            "web": {
                "results": [
                    {
                        "title": "NVIDIA results",
                        "url": "https://nvidianews.nvidia.com/news/results",
                        "description": "NVIDIA announced quarterly results.",
                        "age": "2 days ago",
                    }
                ]
            }
        }

    adapter = BraveSearchAdapter(
        _registry().get("brave_search"),
        raw_dir=tmp_path / "raw",
        options={"queries": ["NVDA earnings"], "count": 1},
        fetch_json=fake_fetch,
    )

    batch = adapter.fetch()

    assert batch.ok is True
    assert batch.output_kind is OutputKind.SEARCH_LEAD
    assert batch.records[0]["source_family_id"] == "provider:brave_search"
    assert batch.records[0]["snippet"] == "NVIDIA announced quarterly results."


def test_search_runner_does_not_create_ledger_outputs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "secret")

    class FakeTavilyAdapter(TavilySearchAdapter):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(
                *args,
                **kwargs,
                post_json=lambda url, headers, payload, timeout: {
                    "results": [
                        {
                            "title": "Apple results",
                            "url": "https://www.apple.com/newsroom/results/",
                            "content": "Apple announced quarterly results.",
                        }
                    ]
                },
            )

    result = run_ingestion(
        registry=_registry(),
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260629T110000Z",
        adapter_classes={"tavily": FakeTavilyAdapter},
        source_ids=("tavily",),
        source_options={"tavily": {"queries": ["AAPL earnings"]}},
        write_ledger=True,
        write_events=True,
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / "normalized" / "search_leads.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert result.manifest.sources[0].derived_outputs == ()
    assert rows[0]["source_id"] == "tavily"
    assert not (tmp_path / "normalized" / "claims.jsonl").exists()
