import json

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
