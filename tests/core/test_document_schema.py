from datetime import datetime, timezone
import hashlib

import pytest
from pydantic import ValidationError

from packages.core import (
    Document,
    DocumentEntity,
    EntityKind,
    SourceTier,
    SourceType,
    make_issuer_family_id,
    make_content_hash,
    make_doc_id,
)


def _retrieved_at() -> datetime:
    return datetime(2026, 6, 27, 8, 30, tzinfo=timezone.utc)


def test_sec_filing_document_records_regulatory_provenance() -> None:
    doc = Document(
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
        published_at=datetime(2026, 5, 1, 22, 3, tzinfo=timezone.utc),
        retrieved_at=_retrieved_at(),
        raw_object_uri="data/raw/sec_edgar/0000320193/0000320193-26-000013/aapl-20260328.htm",
        content_hash=make_content_hash(b"<html>Apple 10-Q</html>"),
        parser_version="sec_edgar_v0.1",
        language="en",
        entities=[
            DocumentEntity(kind=EntityKind.COMPANY, value="Apple Inc."),
            DocumentEntity(kind=EntityKind.TICKER, value="AAPL"),
            DocumentEntity(kind=EntityKind.CIK, value="0000320193"),
        ],
        metadata={
            "accession_number": "0000320193-26-000013",
            "form": "10-Q",
            "primary_document": "aapl-20260328.htm",
        },
    )

    assert doc.doc_id == "sec:0000320193:0000320193-26-000013:aapl-20260328.htm"
    assert doc.source_type is SourceType.SEC_FILING
    assert doc.source_tier is SourceTier.REGULATORY_PRIMARY
    assert doc.metadata["form"] == "10-Q"


def test_sec_exhibit_keeps_same_issuer_family_as_parent_filing() -> None:
    doc = Document(
        doc_id=make_doc_id(
            "sec",
            "0000789019",
            "0000950170-26-012345",
            "msft-ex991.htm",
        ),
        source_id="sec_edgar",
        source_type=SourceType.SEC_EXHIBIT,
        source_tier=SourceTier.REGULATORY_PRIMARY,
        source_family_id=make_issuer_family_id("0000789019"),
        title="Microsoft earnings release exhibit EX-99.1",
        url="https://www.sec.gov/Archives/edgar/data/789019/000095017026012345/msft-ex991.htm",
        published_at=datetime(2026, 4, 24, 20, 10, tzinfo=timezone.utc),
        retrieved_at=_retrieved_at(),
        raw_object_uri="data/raw/sec_edgar/0000789019/0000950170-26-012345/msft-ex991.htm",
        content_hash=make_content_hash("Microsoft earnings release"),
        parser_version="sec_edgar_v0.1",
        entities=[
            DocumentEntity(kind=EntityKind.TICKER, value="MSFT"),
            DocumentEntity(kind=EntityKind.FORM, value="8-K"),
        ],
        metadata={
            "parent_form": "8-K",
            "exhibit_type": "EX-99.1",
            "accession_number": "0000950170-26-012345",
        },
    )

    assert doc.source_family_id == "issuer:0000789019"
    assert doc.source_type is SourceType.SEC_EXHIBIT
    assert doc.metadata["exhibit_type"] == "EX-99.1"


def test_press_release_wire_is_a_document_but_not_independent_confirmation() -> None:
    doc = Document(
        doc_id=make_doc_id("prnewswire", "aapl", "ios-brazil-2026"),
        source_id="prnewswire",
        source_type=SourceType.PRESS_RELEASE_WIRE,
        source_tier=SourceTier.COMPANY_DISTRIBUTED,
        source_family_id=make_issuer_family_id("0000320193"),
        title="Apple announces changes to iOS in Brazil",
        url="https://www.prnewswire.com/news-releases/apple-announces-changes-to-ios-in-brazil.html",
        published_at=datetime(2026, 6, 18, 14, 59, tzinfo=timezone.utc),
        retrieved_at=_retrieved_at(),
        raw_object_uri="data/raw/company_ir/prnewswire/apple-ios-brazil.xml",
        content_hash=make_content_hash("Apple announces changes to iOS in Brazil"),
        parser_version="rss_atom_v0.1",
        entities=[
            DocumentEntity(kind=EntityKind.COMPANY, value="Apple Inc."),
            DocumentEntity(kind=EntityKind.TICKER, value="AAPL"),
        ],
        metadata={
            "wire_publisher": "PR Newswire",
            "feed_url": "https://www.prnewswire.com/rss/news-releases-list.rss",
        },
    )

    assert doc.source_type is SourceType.PRESS_RELEASE_WIRE
    assert doc.source_tier is SourceTier.COMPANY_DISTRIBUTED
    assert doc.source_family_id == "issuer:0000320193"


def test_document_requires_timezone_aware_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        Document(
            doc_id=make_doc_id("sec", "0000320193", "naive-time"),
            source_id="sec_edgar",
            source_type=SourceType.SEC_FILING,
            source_tier=SourceTier.REGULATORY_PRIMARY,
            source_family_id=make_issuer_family_id("0000320193"),
            title="Naive datetime should fail",
            url="https://www.sec.gov/example.htm",
            published_at=datetime(2026, 5, 1, 22, 3),
            retrieved_at=_retrieved_at(),
            raw_object_uri="data/raw/sec_edgar/example.htm",
            content_hash=make_content_hash("bad timestamp"),
            parser_version="sec_edgar_v0.1",
        )


def test_document_rejects_non_document_source_types() -> None:
    with pytest.raises(ValidationError, match="not a document source_type"):
        Document(
            doc_id=make_doc_id("tavily", "aapl", "search-result"),
            source_id="tavily",
            source_type=SourceType.SEARCH,
            source_tier=SourceTier.SEARCH_LEAD,
            source_family_id="provider:tavily",
            title="Apple search result",
            url="https://example.com/apple-search-result",
            published_at=datetime(2026, 6, 18, 14, 59, tzinfo=timezone.utc),
            retrieved_at=_retrieved_at(),
            raw_object_uri="data/raw/tavily/aapl-search.json",
            content_hash=make_content_hash("search snippet"),
            parser_version="tavily_v0.1",
        )


def test_id_and_hash_helpers_are_stable() -> None:
    assert (
        make_doc_id("SEC", "0000320193", "0000320193-26-000013", "AAPL 8-K.htm")
        == "sec:0000320193:0000320193-26-000013:aapl-8-k.htm"
    )

    expected_hash = hashlib.sha256(b"Apple").hexdigest()
    assert make_content_hash("Apple") == f"sha256:{expected_hash}"


def test_document_rejects_invalid_source_type_tier_pair() -> None:
    with pytest.raises(ValidationError, match="not valid for source_type"):
        Document(
            doc_id=make_doc_id("sec", "0000320193", "bad-tier"),
            source_id="sec_edgar",
            source_type=SourceType.SEC_FILING,
            source_tier=SourceTier.COMPANY_DISTRIBUTED,
            source_family_id=make_issuer_family_id("0000320193"),
            title="SEC filing with an impossible tier",
            url="https://www.sec.gov/example.htm",
            published_at=datetime(2026, 5, 1, 22, 3, tzinfo=timezone.utc),
            retrieved_at=_retrieved_at(),
            raw_object_uri="data/raw/sec_edgar/example.htm",
            content_hash=make_content_hash("bad tier"),
            parser_version="sec_edgar_v0.1",
        )


def test_document_requires_canonical_source_family_id() -> None:
    with pytest.raises(ValidationError, match="source_family_id"):
        Document(
            doc_id=make_doc_id("sec", "0000320193", "bad-family"),
            source_id="sec_edgar",
            source_type=SourceType.SEC_FILING,
            source_tier=SourceTier.REGULATORY_PRIMARY,
            source_family_id="issuer:AAPL",
            title="SEC filing with non-canonical family id",
            url="https://www.sec.gov/example.htm",
            published_at=datetime(2026, 5, 1, 22, 3, tzinfo=timezone.utc),
            retrieved_at=_retrieved_at(),
            raw_object_uri="data/raw/sec_edgar/example.htm",
            content_hash=make_content_hash("bad family"),
            parser_version="sec_edgar_v0.1",
        )
