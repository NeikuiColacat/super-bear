from datetime import datetime, timezone

from packages.core import (
    Document,
    SourceTier,
    SourceType,
    make_content_hash,
    make_doc_id,
    make_issuer_family_id,
)
from packages.ingestion.chunker import (
    chunk_document_record,
    chunk_text,
    extract_text_for_chunking,
)


def _document() -> Document:
    return Document(
        doc_id=make_doc_id("sec", "0000320193", "0000320193-26-000013"),
        source_id="sec_edgar",
        source_type=SourceType.SEC_FILING,
        source_tier=SourceTier.REGULATORY_PRIMARY,
        source_family_id=make_issuer_family_id("0000320193"),
        title="Apple Inc. 10-Q filed 2026-05-01",
        url="https://www.sec.gov/example.htm",
        published_at=datetime(2026, 5, 1, 22, 3, tzinfo=timezone.utc),
        retrieved_at=datetime(2026, 6, 28, 8, 30, tzinfo=timezone.utc),
        raw_object_uri="data/raw/sec_edgar/0000320193/submissions.json",
        content_hash=make_content_hash("document metadata"),
        parser_version="sec_submissions_v0.1",
    )


def test_chunk_text_preserves_offsets_into_the_original_text() -> None:
    document = _document()
    text = (
        "Revenue increased across Services and iPhone. "
        "The company also discussed capital returns. "
        "Management noted foreign exchange headwinds."
    )

    chunks = chunk_text(
        document=document,
        text=text,
        max_chars=52,
        overlap_chars=0,
        section_label="body",
    )

    assert len(chunks) == 3
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert [chunk.chunk_id for chunk in chunks] == [
        f"{document.doc_id}:chunk:000000",
        f"{document.doc_id}:chunk:000001",
        f"{document.doc_id}:chunk:000002",
    ]
    for chunk in chunks:
        assert text[chunk.char_start : chunk.char_end] == chunk.text
        assert chunk.content_hash == make_content_hash(chunk.text)
        assert chunk.section_label == "body"


def test_chunk_text_can_overlap_without_breaking_offsets() -> None:
    document = _document()
    text = " ".join(f"token{i:02d}" for i in range(20))

    chunks = chunk_text(
        document=document,
        text=text,
        max_chars=44,
        overlap_chars=8,
    )

    assert len(chunks) > 1
    for previous, current in zip(chunks, chunks[1:]):
        assert current.char_start < previous.char_end
        assert text[current.char_start : current.char_end] == current.text


def test_chunk_text_overlap_does_not_start_in_the_middle_of_a_word() -> None:
    document = _document()
    text = "Alpha revenue increased materially. Beta revenue increased materially."

    chunks = chunk_text(
        document=document,
        text=text,
        max_chars=38,
        overlap_chars=8,
    )

    assert len(chunks) > 1
    for chunk in chunks[1:]:
        assert text[chunk.char_start - 1].isspace()
        assert text[chunk.char_start : chunk.char_end] == chunk.text


def test_extract_text_for_chunking_prefers_primary_raw_html(tmp_path) -> None:
    raw_path = tmp_path / "raw" / "sec_edgar" / "0000320193" / "filing.htm"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(
        """
        <html>
          <head><style>.hidden{display:none}</style></head>
          <body>
            <ix:hidden>ignore xbrl header</ix:hidden>
            <p>UNITED STATES SECURITIES AND EXCHANGE COMMISSION</p>
            <p>Apple Inc. quarterly report body.</p>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    record = _document().model_dump(mode="json")
    record["metadata"]["primary_document_raw_uri"] = str(raw_path)
    record["metadata"]["primary_document_text_excerpt"] = "fallback excerpt"

    extracted = extract_text_for_chunking(record)

    assert extracted is not None
    assert extracted.source == "metadata.primary_document_raw_uri"
    assert "Apple Inc. quarterly report body." in extracted.text
    assert "fallback excerpt" not in extracted.text


def test_extract_text_for_chunking_prefers_company_ir_article_body(tmp_path) -> None:
    raw_path = tmp_path / "apple-newsroom.html"
    raw_path.write_text(
        """
        <html>
          <body>
            <nav><img src="/logo.svg">Apple Store Mac iPad iPhone Watch</nav>
            <article>
              <h1>Apple announces services update</h1>
              <p>Apple said revenue increased year over year.</p>
            </article>
            <footer>Copyright and support links</footer>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    record = _document().model_dump(mode="json")
    record["source_id"] = "company_ir"
    record["source_type"] = "company_newsroom"
    record["source_tier"] = "company_primary"
    record["source_family_id"] = "issuer:0000320193"
    record["metadata"]["primary_document_raw_uri"] = str(raw_path)

    extracted = extract_text_for_chunking(record)

    assert extracted is not None
    assert extracted.text.startswith("Apple announces services update")
    assert "Apple Store Mac" not in extracted.text
    assert "Copyright and support" not in extracted.text


def test_chunk_document_record_uses_available_text_and_keeps_document_provenance(
    tmp_path,
) -> None:
    raw_path = tmp_path / "filing.htm"
    raw_path.write_text(
        "<html><body>First filing sentence. Second filing sentence.</body></html>",
        encoding="utf-8",
    )
    record = _document().model_dump(mode="json")
    record["metadata"]["primary_document_raw_uri"] = str(raw_path)

    chunks = chunk_document_record(record, max_chars=28, overlap_chars=0)

    assert len(chunks) == 2
    assert all(chunk.doc_id == record["doc_id"] for chunk in chunks)
    assert chunks[0].metadata["text_source"] == "metadata.primary_document_raw_uri"
    assert chunks[0].metadata["document_title"] == record["title"]
    assert chunks[0].metadata["primary_document_raw_uri"] == str(raw_path)
    source_text = extract_text_for_chunking(record).text
    for chunk in chunks:
        assert source_text[chunk.char_start : chunk.char_end] == chunk.text
