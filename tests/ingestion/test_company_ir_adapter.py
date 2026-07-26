import json
from datetime import datetime, timezone

from packages.core import OutputKind, SourceTier, SourceType
from packages.ingestion.adapters.company_ir import CompanyIrAdapter
from packages.ingestion.registry import SourceRegistry
from packages.ingestion.runner import run_ingestion


RSS_FEED = b"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>Apple Newsroom</title>
    <item>
      <title>Apple reports quarterly results</title>
      <link>https://www.apple.com/newsroom/2026/results/</link>
      <guid>apple-results</guid>
      <pubDate>Mon, 29 Jun 2026 13:00:00 GMT</pubDate>
      <description><![CDATA[<p>Revenue increased year over year.</p>]]></description>
    </item>
    <item>
      <title>Apple announces product update</title>
      <link>https://www.apple.com/newsroom/2026/product/</link>
      <guid>apple-product</guid>
      <pubDate>Tue, 30 Jun 2026 13:00:00 GMT</pubDate>
      <description>New product announced.</description>
    </item>
  </channel>
</rss>
"""


ATOM_FEED = b"""<?xml version="1.0" encoding="UTF-8" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>NVIDIA News</title>
  <entry>
    <title>NVIDIA announces quarterly results</title>
    <link href="https://nvidianews.nvidia.com/news/results" />
    <id>nvidia-results</id>
    <updated>2026-06-29T13:00:00Z</updated>
    <summary>NVIDIA reported revenue growth.</summary>
  </entry>
</feed>
"""


RELATIVE_LINK_FEED = b"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>Netflix Investor Relations</title>
    <item>
      <title>Netflix releases investor document</title>
      <link>/files/doc_news/2026/release.pdf</link>
      <pubDate>Mon, 29 Jun 2026 13:00:00 GMT</pubDate>
      <description>Investor document.</description>
    </item>
  </channel>
</rss>
"""


def _registry() -> SourceRegistry:
    return SourceRegistry.from_yaml("configs/sources.yaml")


def test_company_ir_adapter_parses_rss_feed_to_documents(tmp_path) -> None:
    adapter = CompanyIrAdapter(
        _registry().get("company_ir"),
        raw_dir=tmp_path / "raw",
        options={
            "issuers": [
                {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "feeds": [
                        {
                            "url": "https://www.apple.com/newsroom/rss-feed.rss",
                            "source_type": "company_newsroom",
                        }
                    ],
                }
            ]
        },
        fetch_bytes=lambda url, headers, timeout: RSS_FEED,
    )

    batch = adapter.fetch(limit=2)

    assert batch.ok is True
    assert batch.output_kind is OutputKind.DOCUMENT
    assert len(batch.records) == 2
    first = batch.records[0]
    assert first["source_type"] == SourceType.COMPANY_NEWSROOM
    assert first["source_tier"] == SourceTier.COMPANY_PRIMARY
    assert first["source_family_id"] == "issuer_ticker:AAPL"
    assert first["metadata"]["primary_document_text"] == (
        "Revenue increased year over year."
    )
    assert first["entities"][0]["value"] == "AAPL"
    assert batch.raw_uris[0].endswith(".xml")


def test_company_ir_adapter_parses_atom_feed_to_documents(tmp_path) -> None:
    adapter = CompanyIrAdapter(
        _registry().get("company_ir"),
        raw_dir=tmp_path / "raw",
        options={
            "issuers": [
                {
                    "ticker": "NVDA",
                    "company_name": "NVIDIA Corporation",
                    "feeds": [
                        {
                            "url": "https://nvidianews.nvidia.com/news/rss",
                            "source_type": "company_ir",
                        }
                    ],
                }
            ]
        },
        fetch_bytes=lambda url, headers, timeout: ATOM_FEED,
    )

    batch = adapter.fetch(limit=1)

    assert batch.ok is True
    assert len(batch.records) == 1
    assert batch.records[0]["title"] == "NVIDIA announces quarterly results"
    assert batch.records[0]["metadata"]["primary_document_text"] == (
        "NVIDIA reported revenue growth."
    )


def test_company_ir_adapter_resolves_relative_feed_links(tmp_path) -> None:
    adapter = CompanyIrAdapter(
        _registry().get("company_ir"),
        raw_dir=tmp_path / "raw",
        options={
            "issuers": [
                {
                    "ticker": "NFLX",
                    "company_name": "Netflix, Inc.",
                    "feeds": [
                        {
                            "url": "https://ir.netflix.net/rss/PressRelease.aspx",
                            "source_type": "company_ir",
                        }
                    ],
                }
            ]
        },
        fetch_bytes=lambda url, headers, timeout: RELATIVE_LINK_FEED,
    )

    batch = adapter.fetch(limit=1)

    assert batch.ok is True
    assert batch.records[0]["url"] == (
        "https://ir.netflix.net/files/doc_news/2026/release.pdf"
    )


def test_company_ir_adapter_can_store_item_page_as_primary_raw(tmp_path) -> None:
    requests: list[str] = []
    sleeps: list[float] = []

    def fake_fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        requests.append(url)
        if url == "https://www.apple.com/newsroom/rss-feed.rss":
            return RSS_FEED
        return (
            b"<html><body>Detailed results page says revenue increased.</body></html>"
        )

    adapter = CompanyIrAdapter(
        _registry().get("company_ir"),
        raw_dir=tmp_path / "raw",
        options={
            "fetch_item_pages": True,
            "issuers": [
                {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "feeds": [
                        {
                            "url": "https://www.apple.com/newsroom/rss-feed.rss",
                            "source_type": "company_newsroom",
                        }
                    ],
                }
            ],
        },
        fetch_bytes=fake_fetch,
        sleep=sleeps.append,
    )

    batch = adapter.fetch(limit=1)

    assert batch.ok is True
    assert requests == [
        "https://www.apple.com/newsroom/rss-feed.rss",
        "https://www.apple.com/newsroom/2026/results/",
    ]
    assert sleeps == [1.0]
    record = batch.records[0]
    metadata = record["metadata"]
    assert record["raw_object_uri"].endswith(".html")
    assert metadata["feed_raw_object_uri"].endswith(".xml")
    assert metadata["primary_document_raw_uri"] == record["raw_object_uri"]
    assert metadata["primary_document_content_hash"] == record["content_hash"]
    assert b"Detailed results page" in open(record["raw_object_uri"], "rb").read()


def test_company_ir_adapter_requires_issuers_before_fetch(tmp_path) -> None:
    adapter = CompanyIrAdapter(
        _registry().get("company_ir"),
        raw_dir=tmp_path / "raw",
        options={},
        fetch_bytes=lambda url, headers, timeout: RSS_FEED,
    )

    batch = adapter.fetch()

    assert batch.ok is False
    assert batch.error is not None
    assert batch.error.code == "missing_source_options"


def test_company_ir_adapter_loads_issuers_from_catalog_path(tmp_path) -> None:
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
""",
        encoding="utf-8",
    )
    adapter = CompanyIrAdapter(
        _registry().get("company_ir"),
        raw_dir=tmp_path / "raw",
        options={"catalog_path": str(catalog_path)},
        fetch_bytes=lambda url, headers, timeout: RSS_FEED,
    )

    batch = adapter.fetch(limit=1)

    assert batch.ok is True
    assert len(batch.records) == 1
    assert batch.records[0]["source_family_id"] == "issuer:0000320193"


def test_company_ir_adapter_filters_old_feed_items_for_daily_runs(tmp_path) -> None:
    adapter = CompanyIrAdapter(
        _registry().get("company_ir"),
        raw_dir=tmp_path / "raw",
        options={
            "published_after": datetime(2026, 6, 30, tzinfo=timezone.utc),
            "issuers": [
                {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "feeds": [
                        {
                            "url": "https://www.apple.com/newsroom/rss-feed.rss",
                            "source_type": "company_newsroom",
                        }
                    ],
                }
            ],
        },
        fetch_bytes=lambda url, headers, timeout: RSS_FEED,
    )

    batch = adapter.fetch()

    assert batch.ok is True
    assert [record["title"] for record in batch.records] == [
        "Apple announces product update"
    ]


def test_company_ir_adapter_warns_when_feed_items_are_filtered_out(tmp_path) -> None:
    adapter = CompanyIrAdapter(
        _registry().get("company_ir"),
        raw_dir=tmp_path / "raw",
        options={
            "published_after": datetime(2026, 7, 1, tzinfo=timezone.utc),
            "issuers": [
                {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "feeds": [
                        {
                            "url": "https://www.apple.com/newsroom/rss-feed.rss",
                            "source_type": "company_newsroom",
                        }
                    ],
                }
            ],
        },
        fetch_bytes=lambda url, headers, timeout: RSS_FEED,
    )

    batch = adapter.fetch()

    assert batch.ok is True
    assert batch.records == ()
    assert batch.warnings
    warning = batch.warnings[0]
    assert warning.code == "feed_no_records"
    assert warning.retryable is False
    assert warning.details["ticker"] == "AAPL"
    assert warning.details["raw_item_count"] == 2
    assert warning.details["filtered_by_published_after_count"] == 2
    assert warning.details["records_written"] == 0
    assert warning.details["latest_item_published_at"] == "2026-06-30T13:00:00Z"


def test_company_ir_adapter_continues_after_one_feed_failure(tmp_path) -> None:
    def fake_fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        if "bad.example" in url:
            raise OSError("temporary outage")
        return RSS_FEED

    adapter = CompanyIrAdapter(
        _registry().get("company_ir"),
        raw_dir=tmp_path / "raw",
        options={
            "issuers": [
                {
                    "ticker": "MSFT",
                    "company_name": "Microsoft Corporation",
                    "feeds": [
                        {
                            "url": "https://bad.example/rss",
                            "source_type": "company_ir",
                        }
                    ],
                },
                {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "feeds": [
                        {
                            "url": "https://www.apple.com/newsroom/rss-feed.rss",
                            "source_type": "company_newsroom",
                        }
                    ],
                },
            ]
        },
        fetch_bytes=fake_fetch,
    )

    batch = adapter.fetch(limit=1)

    assert batch.ok is True
    assert len(batch.records) == 1
    assert batch.records[0]["entities"][0]["value"] == "AAPL"
    assert batch.warnings[0].code == "feed_error"
    assert batch.warnings[0].details["ticker"] == "MSFT"


def test_company_ir_adapter_continues_after_one_parse_failure(tmp_path) -> None:
    def fake_fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        if "bad.example" in url:
            return b"<rss><channel><item></channel>"
        return RSS_FEED

    adapter = CompanyIrAdapter(
        _registry().get("company_ir"),
        raw_dir=tmp_path / "raw",
        options={
            "issuers": [
                {
                    "ticker": "MSFT",
                    "company_name": "Microsoft Corporation",
                    "feeds": [
                        {
                            "url": "https://bad.example/rss",
                            "source_type": "company_ir",
                        }
                    ],
                },
                {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "feeds": [
                        {
                            "url": "https://www.apple.com/newsroom/rss-feed.rss",
                            "source_type": "company_newsroom",
                        }
                    ],
                },
            ]
        },
        fetch_bytes=fake_fetch,
    )

    batch = adapter.fetch(limit=1)

    assert batch.ok is True
    assert len(batch.records) == 1
    assert batch.records[0]["entities"][0]["value"] == "AAPL"
    assert batch.warnings[0].code == "feed_parse_error"
    assert batch.warnings[0].details["ticker"] == "MSFT"


def test_company_ir_adapter_rate_limits_between_feed_requests(tmp_path) -> None:
    sleeps: list[float] = []
    urls: list[str] = []

    def fake_fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        urls.append(url)
        return RSS_FEED

    adapter = CompanyIrAdapter(
        _registry().get("company_ir"),
        raw_dir=tmp_path / "raw",
        options={
            "issuers": [
                {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "feeds": [
                        {
                            "url": "https://example.com/one.xml",
                            "source_type": "company_newsroom",
                        },
                        {
                            "url": "https://example.com/two.xml",
                            "source_type": "company_newsroom",
                        },
                    ],
                }
            ]
        },
        fetch_bytes=fake_fetch,
        sleep=sleeps.append,
    )

    batch = adapter.fetch()

    assert batch.ok is True
    assert urls == ["https://example.com/one.xml", "https://example.com/two.xml"]
    assert sleeps == [1.0]


def test_company_ir_runner_writes_documents_and_chunks(tmp_path) -> None:
    class FakeCompanyIrAdapter(CompanyIrAdapter):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(
                *args,
                **kwargs,
                fetch_bytes=lambda url, headers, timeout: RSS_FEED,
            )

    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260629T090000Z",
        adapter_classes={"company_ir": FakeCompanyIrAdapter},
        source_ids=("company_ir",),
        source_options={
            "company_ir": {
                "issuers": [
                    {
                        "ticker": "AAPL",
                        "company_name": "Apple Inc.",
                        "feeds": [
                            {
                                "url": "https://www.apple.com/newsroom/rss-feed.rss",
                                "source_type": "company_newsroom",
                            }
                        ],
                    }
                ]
            }
        },
        write_chunks=True,
    )

    documents = [
        json.loads(line)
        for line in (tmp_path / "normalized" / "documents.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    chunks = [
        json.loads(line)
        for line in (tmp_path / "normalized" / "document_chunks.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert result.manifest.sources[0].status == "success"
    assert result.manifest.sources[0].derived_outputs[0].records_written == 2
    assert documents[0]["source_id"] == "company_ir"
    assert chunks[0]["text"] == "Revenue increased year over year."
