from datetime import datetime, timezone
import json

from packages.core import (
    Document,
    OutputKind,
    SourceTier,
    SourceType,
    make_content_hash,
    make_doc_id,
    make_issuer_family_id,
)
from packages.ingestion.adapters.base import (
    AdapterBatch,
    AdapterError,
    BaseSourceAdapter,
)
from packages.ingestion.registry import SourceRegistry
from packages.ingestion.runner import main, run_ingestion


def _ts(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 28, hour, minute, tzinfo=timezone.utc)


class FailingSecAdapter(BaseSourceAdapter):
    source_id = "sec_edgar"

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        return AdapterBatch.failure(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            retrieved_at=_ts(8, 1),
            error=AdapterError(
                code="network_timeout",
                message="SEC request timed out",
                retryable=True,
            ),
        )


class EmptySecAdapter(BaseSourceAdapter):
    source_id = "sec_edgar"

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            retrieved_at=_ts(8, 1),
            records=[],
            raw_uris=[],
        )


class InspectingSecAdapter(BaseSourceAdapter):
    source_id = "sec_edgar"

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        assert self.raw_dir is not None
        assert self.options["ciks"] == ["0000320193"]
        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            retrieved_at=_ts(8, 1),
            records=[],
            raw_uris=[
                str(self.raw_dir / "sec_edgar" / "0000320193" / "submissions.json")
            ],
        )


class PreviewSecAdapter(BaseSourceAdapter):
    source_id = "sec_edgar"

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            retrieved_at=_ts(8, 1),
            records=[
                {
                    "doc_id": "sec:apple:10q",
                    "title": "Apple Inc. 10-Q filed 2026-05-01",
                    "url": "https://www.sec.gov/aapl-10q.htm",
                    "metadata": {"form": "10-Q"},
                },
                {
                    "doc_id": "sec:apple:8k",
                    "title": "Apple Inc. 8-K filed 2026-04-30",
                    "url": "https://www.sec.gov/aapl-8k.htm",
                    "metadata": {"form": "8-K"},
                },
            ],
            raw_uris=["data/raw/sec_edgar/0000320193/submissions.json"],
        )


class ChunkingSecAdapter(BaseSourceAdapter):
    source_id = "sec_edgar"

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        assert self.raw_dir is not None
        raw_path = (
            self.raw_dir
            / "sec_edgar"
            / "0000320193"
            / "000032019326000013"
            / "aapl-20260328.htm"
        )
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(
            """
            <html>
              <body>
                <p>First filing sentence.</p>
                <p>Net sales increased year over year.</p>
              </body>
            </html>
            """,
            encoding="utf-8",
        )
        document = Document(
            doc_id=make_doc_id(
                "sec",
                "0000320193",
                "0000320193-26-000013",
                "aapl-20260328.htm",
            ),
            source_id="sec_edgar",
            source_type=SourceType.SEC_FILING,
            source_tier=SourceTier.REGULATORY_PRIMARY,
            source_family_id=make_issuer_family_id("0000320193"),
            title="Apple Inc. 10-Q filed 2026-05-01",
            url="https://www.sec.gov/Archives/edgar/data/320193/000032019326000013/aapl-20260328.htm",
            published_at=_ts(8, 1),
            retrieved_at=_ts(8, 1),
            raw_object_uri="data/raw/sec_edgar/0000320193/submissions.json",
            content_hash=make_content_hash("document metadata"),
            parser_version="sec_submissions_v0.1",
            metadata={
                "form": "10-Q",
                "primary_document_raw_uri": str(raw_path),
            },
        )
        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            retrieved_at=_ts(8, 1),
            records=[document.model_dump(mode="json")],
            raw_uris=[str(raw_path)],
        )


class ChunkingCompanyIrAdapter(BaseSourceAdapter):
    source_id = "company_ir"

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        assert self.raw_dir is not None
        raw_path = self.raw_dir / "company_ir" / "MSFT" / "earnings-release.html"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(
            """
            <html>
              <body>
                <p>Microsoft revenue increased year over year.</p>
              </body>
            </html>
            """,
            encoding="utf-8",
        )
        document = Document(
            doc_id=make_doc_id("ir", "MSFT", "earnings-release"),
            source_id="company_ir",
            source_type=SourceType.COMPANY_EARNINGS_RELEASE,
            source_tier=SourceTier.COMPANY_PRIMARY,
            source_family_id=make_issuer_family_id("0000789019"),
            title="Microsoft earnings release",
            url="https://www.microsoft.com/en-us/investor/earnings",
            published_at=_ts(8, 5),
            retrieved_at=_ts(8, 5),
            raw_object_uri=str(raw_path),
            content_hash=make_content_hash("microsoft earnings metadata"),
            parser_version="company_ir_feed_v0.1",
            metadata={"primary_document_raw_uri": str(raw_path)},
        )
        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            retrieved_at=_ts(8, 5),
            records=[document.model_dump(mode="json")],
            raw_uris=[str(raw_path)],
        )


def test_runner_executes_available_adapters_and_skips_unimplemented_sources(
    tmp_path,
) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": EmptySecAdapter},
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    assert result.manifest.run_id == "run_20260628T080000Z"
    assert result.manifest_path == (
        tmp_path / "runs" / "run_20260628T080000Z" / "manifest.json"
    )
    assert [source.source_id for source in result.manifest.sources] == [
        "sec_edgar",
        "company_ir",
        "yfinance",
        "tavily",
        "brave_search",
        "stock_sentiment",
    ]

    sec = result.manifest.sources[0]
    assert sec.status == "success"
    assert sec.records_seen == 0
    assert sec.records_written == 0
    assert sec.skipped_reason == "no_records"
    assert sec.output_path == str(tmp_path / "normalized" / "documents.jsonl")

    skipped = result.manifest.sources[1:]
    assert {source.status for source in skipped} == {"skipped"}
    assert {source.skipped_reason for source in skipped} == {"adapter_not_implemented"}

    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert payload["sources"][0]["source_id"] == "sec_edgar"
    assert payload["sources"][0]["status"] == "success"
    assert payload["sources"][1]["status"] == "skipped"


def test_runner_records_failed_adapter_batch(tmp_path) -> None:
    registry = SourceRegistry.from_items(
        [
            {
                "source_id": "sec_edgar",
                "enabled": True,
                "adapter": "sec_edgar",
                "output_kind": "document",
                "default_source_type": "sec_filing",
                "allowed_source_types": ["sec_filing"],
                "source_tier": "regulatory_primary",
                "source_family_strategy": "issuer",
                "requires_api_key": False,
                "rate_limit_per_second": 8,
                "license_notes": "test source",
            }
        ]
    )

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": FailingSecAdapter},
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    source_result = result.manifest.sources[0]
    assert source_result.status == "failed"
    assert source_result.records_seen == 0
    assert source_result.records_written == 0
    assert source_result.output_kind is OutputKind.DOCUMENT
    assert source_result.error is not None
    assert source_result.error.code == "network_timeout"
    assert source_result.skipped_reason == "batch_failed"


def test_runner_can_limit_sources_from_run_config(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": EmptySecAdapter},
        source_ids=("sec_edgar",),
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    assert [source.source_id for source in result.manifest.sources] == ["sec_edgar"]


def test_runner_passes_raw_dir_and_source_options_to_adapter(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": InspectingSecAdapter},
        source_ids=("sec_edgar",),
        source_options={"sec_edgar": {"ciks": ["0000320193"]}},
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    assert result.manifest.sources[0].raw_uris == (
        str(tmp_path / "raw" / "sec_edgar" / "0000320193" / "submissions.json"),
    )


def test_runner_collects_cli_previews_from_current_batches(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": PreviewSecAdapter},
        source_ids=("sec_edgar",),
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    preview = result.cli_previews[0]
    assert preview.source_id == "sec_edgar"
    assert preview.records_written == 2
    assert preview.output_path == str(tmp_path / "normalized" / "documents.jsonl")
    assert preview.raw_uris == ("data/raw/sec_edgar/0000320193/submissions.json",)
    assert preview.form_counts == {"10-Q": 1, "8-K": 1}
    assert [sample.title for sample in preview.samples] == [
        "Apple Inc. 10-Q filed 2026-05-01",
        "Apple Inc. 8-K filed 2026-04-30",
    ]


def test_runner_cli_uses_yaml_config_and_prints_summary(tmp_path, capsys) -> None:
    config_path = tmp_path / "ingestion_run.yaml"
    config_path.write_text(
        f"""
version: 1
source_registry_path: configs/sources.yaml
raw_dir: {tmp_path / "raw"}
normalized_dir: {tmp_path / "normalized"}
runs_dir: {tmp_path / "runs"}
default_limit: null
enabled_source_ids:
  - sec_edgar
  - tavily
skip_unimplemented_adapters: true
source_options:
  sec_edgar:
    ciks:
      - "0000320193"
  tavily:
    queries:
      - "AAPL earnings"
""",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--run-id",
            "run_20260628T080000Z",
            "--source",
            "tavily",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "CLI preview" in captured.out
    assert "run_id: run_20260628T080000Z" in captured.out
    expected_manifest = tmp_path / "runs" / "run_20260628T080000Z" / "manifest.json"
    assert f"manifest: {expected_manifest}" in captured.out
    assert "- tavily: failed, records_written=0, skipped_reason=batch_failed" in (
        captured.out
    )
    assert "error: missing_api_key" in captured.out

    payload = json.loads(
        (tmp_path / "runs" / "run_20260628T080000Z" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert [source["source_id"] for source in payload["sources"]] == ["tavily"]
    assert payload["sources"][0]["status"] == "failed"
    assert payload["sources"][0]["error"]["code"] == "missing_api_key"


def test_runner_can_write_document_chunks_as_derived_output(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": ChunkingSecAdapter},
        source_ids=("sec_edgar",),
        write_chunks=True,
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    chunks_path = tmp_path / "normalized" / "document_chunks.jsonl"
    chunk_records = [
        json.loads(line)
        for line in chunks_path.read_text(encoding="utf-8").splitlines()
    ]

    assert len(chunk_records) == 1
    assert chunk_records[0]["chunk_id"].endswith(":chunk:000000")
    assert (
        chunk_records[0]["text"]
        == "First filing sentence. Net sales increased year over year."
    )
    assert (
        chunk_records[0]["metadata"]["text_source"]
        == "metadata.primary_document_raw_uri"
    )

    derived = result.manifest.sources[0].derived_outputs[0]
    assert derived.output_kind is OutputKind.DOCUMENT_CHUNK
    assert derived.output_path == str(chunks_path)
    assert derived.records_written == 1

    preview = result.cli_previews[0]
    assert preview.derived_outputs[0].records_written == 1
    assert preview.chunk_samples[0].text == chunk_records[0]["text"]


def test_runner_overwrites_normalized_outputs_for_each_run(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")
    kwargs = {
        "registry": registry,
        "normalized_dir": tmp_path / "normalized",
        "raw_dir": tmp_path / "raw",
        "runs_dir": tmp_path / "runs",
        "adapter_classes": {"sec_edgar": ChunkingSecAdapter},
        "source_ids": ("sec_edgar",),
        "write_events": True,
        "started_at": _ts(8, 0),
        "finished_at": _ts(8, 2),
    }

    run_ingestion(run_id="run_20260628T080000Z", **kwargs)
    run_ingestion(run_id="run_20260628T080100Z", **kwargs)

    documents = (
        (tmp_path / "normalized" / "documents.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    chunks = (
        (tmp_path / "normalized" / "document_chunks.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    claim_candidates = (
        (tmp_path / "normalized" / "claim_candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    evidence_candidates = (
        (tmp_path / "normalized" / "evidence_span_candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    claims = (
        (tmp_path / "normalized" / "claims.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    evidence_spans = (
        (tmp_path / "normalized" / "evidence_spans.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    events = (
        (tmp_path / "normalized" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )

    assert len(documents) == 1
    assert len(chunks) == 1
    assert len(claim_candidates) == 1
    assert len(evidence_candidates) == 1
    assert len(claims) == 1
    assert len(evidence_spans) == 1
    assert len(events) == 1


def test_runner_clears_stale_ledger_outputs_when_ledger_is_disabled(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")
    kwargs = {
        "registry": registry,
        "normalized_dir": tmp_path / "normalized",
        "raw_dir": tmp_path / "raw",
        "runs_dir": tmp_path / "runs",
        "adapter_classes": {"sec_edgar": ChunkingSecAdapter},
        "source_ids": ("sec_edgar",),
        "started_at": _ts(8, 0),
        "finished_at": _ts(8, 2),
    }

    run_ingestion(
        run_id="run_20260628T080000Z",
        write_events=True,
        **kwargs,
    )
    run_ingestion(
        run_id="run_20260628T080100Z",
        write_ledger=False,
        **kwargs,
    )

    assert not (tmp_path / "normalized" / "claims.jsonl").exists()
    assert not (tmp_path / "normalized" / "evidence_spans.jsonl").exists()
    assert not (tmp_path / "normalized" / "validation_errors.jsonl").exists()
    assert not (tmp_path / "normalized" / "events.jsonl").exists()


def test_runner_clears_stale_events_when_running_non_document_source(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": ChunkingSecAdapter},
        source_ids=("sec_edgar",),
        write_events=True,
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )
    run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080100Z",
        adapter_classes={"sec_edgar": ChunkingSecAdapter},
        source_ids=("tavily",),
        write_events=False,
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    assert not (tmp_path / "normalized" / "events.jsonl").exists()


def test_runner_can_write_claim_and_evidence_candidates(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": ChunkingSecAdapter},
        source_ids=("sec_edgar",),
        write_candidates=True,
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    claim_path = tmp_path / "normalized" / "claim_candidates.jsonl"
    evidence_path = tmp_path / "normalized" / "evidence_span_candidates.jsonl"
    claims = [
        json.loads(line) for line in claim_path.read_text(encoding="utf-8").splitlines()
    ]
    evidence_spans = [
        json.loads(line)
        for line in evidence_path.read_text(encoding="utf-8").splitlines()
    ]

    assert len(claims) == 1
    assert len(evidence_spans) == 1
    assert claims[0]["claim_text"] == "Net sales increased year over year."
    assert evidence_spans[0]["text"] == claims[0]["claim_text"]
    assert evidence_spans[0]["claim_candidate_id"] == claims[0]["claim_candidate_id"]
    assert {
        output.output_kind for output in result.manifest.sources[0].derived_outputs
    } == {
        OutputKind.DOCUMENT_CHUNK,
        OutputKind.CLAIM_CANDIDATE,
        OutputKind.EVIDENCE_SPAN_CANDIDATE,
    }


def test_runner_can_write_pre_event_ledger(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": ChunkingSecAdapter},
        source_ids=("sec_edgar",),
        write_ledger=True,
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    claim_path = tmp_path / "normalized" / "claims.jsonl"
    evidence_path = tmp_path / "normalized" / "evidence_spans.jsonl"
    claims = [
        json.loads(line) for line in claim_path.read_text(encoding="utf-8").splitlines()
    ]
    evidence_spans = [
        json.loads(line)
        for line in evidence_path.read_text(encoding="utf-8").splitlines()
    ]

    assert len(claims) == 1
    assert len(evidence_spans) == 1
    assert claims[0]["event_id"] is None
    assert claims[0]["claim_id"].endswith(":claim:000000")
    assert evidence_spans[0]["claim_id"] == claims[0]["claim_id"]
    assert {
        output.output_kind for output in result.manifest.sources[0].derived_outputs
    } == {
        OutputKind.DOCUMENT_CHUNK,
        OutputKind.CLAIM_CANDIDATE,
        OutputKind.EVIDENCE_SPAN_CANDIDATE,
        OutputKind.CLAIM,
        OutputKind.EVIDENCE_SPAN,
        OutputKind.VALIDATION_ERROR,
    }


def test_runner_can_write_events(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": ChunkingSecAdapter},
        source_ids=("sec_edgar",),
        write_events=True,
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    events_path = tmp_path / "normalized" / "events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]

    assert len(events) == 1
    assert events[0]["event_type"] == "sec_filing"
    assert events[0]["assembly_key"] == "issuer:0000320193|sec_filing|10-Q|20260628"
    assert events[0]["related_doc_ids"]
    assert events[0]["claim_ids"]
    assert {
        output.output_kind for output in result.manifest.sources[0].derived_outputs
    } == {
        OutputKind.DOCUMENT_CHUNK,
        OutputKind.CLAIM_CANDIDATE,
        OutputKind.EVIDENCE_SPAN_CANDIDATE,
        OutputKind.CLAIM,
        OutputKind.EVIDENCE_SPAN,
        OutputKind.VALIDATION_ERROR,
        OutputKind.EVENT,
    }


def test_runner_can_write_event_cards_and_brief(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": ChunkingSecAdapter},
        source_ids=("sec_edgar",),
        write_event_cards=True,
        write_brief=True,
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    cards_path = tmp_path / "normalized" / "event_cards.jsonl"
    brief_path = tmp_path / "normalized" / "briefings.jsonl"
    cards = [
        json.loads(line) for line in cards_path.read_text(encoding="utf-8").splitlines()
    ]
    briefs = [
        json.loads(line) for line in brief_path.read_text(encoding="utf-8").splitlines()
    ]

    assert cards[0]["what_happened"] == "Net sales increased year over year."
    assert cards[0]["key_claim_ids"]
    assert cards[0]["key_evidence_span_ids"]
    assert cards[0]["source_summary"] == ["regulatory_primary:sec_filing"]
    assert briefs[0]["event_card_ids"] == [cards[0]["event_card_id"]]
    assert cards[0]["key_claim_ids"][0] in briefs[0]["markdown"]
    assert {
        output.output_kind for output in result.manifest.sources[0].derived_outputs
    } >= {OutputKind.EVENT, OutputKind.EVENT_CARD, OutputKind.BRIEFING}


def test_runner_writes_one_global_brief_across_document_sources(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={
            "sec_edgar": ChunkingSecAdapter,
            "company_ir": ChunkingCompanyIrAdapter,
        },
        source_ids=("sec_edgar", "company_ir"),
        write_brief=True,
        started_at=_ts(8, 0),
        finished_at=_ts(8, 10),
    )

    cards = [
        json.loads(line)
        for line in (tmp_path / "normalized" / "event_cards.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    briefs = [
        json.loads(line)
        for line in (tmp_path / "normalized" / "briefings.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert len(cards) == 2
    assert len(briefs) == 1
    assert briefs[0]["event_card_ids"] == [card["event_card_id"] for card in cards]
