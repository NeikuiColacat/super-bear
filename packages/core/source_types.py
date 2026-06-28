from enum import StrEnum


class OutputKind(StrEnum):
    DOCUMENT = "document"
    DOCUMENT_CHUNK = "document_chunk"
    CLAIM_CANDIDATE = "claim_candidate"
    EVIDENCE_SPAN_CANDIDATE = "evidence_span_candidate"
    CLAIM = "claim"
    EVIDENCE_SPAN = "evidence_span"
    EVENT = "event"
    EVENT_CARD = "event_card"
    BRIEFING = "briefing"
    INVESTIGATOR_RUN = "investigator_run"
    VALIDATION_ERROR = "validation_error"
    MARKET_CONTEXT = "market_context"
    SEARCH_LEAD = "search_lead"
    ATTENTION_SIGNAL = "attention_signal"


class SourceType(StrEnum):
    SEC_FILING = "sec_filing"
    SEC_EXHIBIT = "sec_exhibit"
    COMPANY_IR = "company_ir"
    COMPANY_NEWSROOM = "company_newsroom"
    COMPANY_EARNINGS_RELEASE = "company_earnings_release"
    PRESS_RELEASE_WIRE = "press_release_wire"
    MARKET_DATA = "market_data"
    SEARCH = "search"
    SOCIAL_SENTIMENT = "social_sentiment"


class SourceTier(StrEnum):
    REGULATORY_PRIMARY = "regulatory_primary"
    COMPANY_PRIMARY = "company_primary"
    COMPANY_DISTRIBUTED = "company_distributed"
    MARKET_CONTEXT = "market_context"
    SEARCH_LEAD = "search_lead"
    ATTENTION_SIGNAL = "attention_signal"


class EntityKind(StrEnum):
    COMPANY = "company"
    TICKER = "ticker"
    CIK = "cik"
    FORM = "form"
    ACCESSION_NUMBER = "accession_number"
    PRODUCT = "product"
    PERSON = "person"
    LOCATION = "location"
    INDUSTRY = "industry"
    OTHER = "other"


class EvidenceRelation(StrEnum):
    SUPPORT = "support"
    REFUTE = "refute"
    UPDATE = "update"
    UNCERTAIN = "uncertain"


class ClaimType(StrEnum):
    FACT = "fact"
    FORECAST = "forecast"
    OPINION = "opinion"
    RUMOR = "rumor"


class ClaimStatus(StrEnum):
    SUPPORTED = "supported"
    REFUTED = "refuted"
    MISSING = "missing"
    CONFLICTING = "conflicting"
    OBSOLETE = "obsolete"


class EventType(StrEnum):
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    SEC_FILING = "sec_filing"
    PRODUCT = "product"
    M_AND_A = "m_and_a"
    REGULATORY = "regulatory"
    LITIGATION = "litigation"
    LEADERSHIP = "leadership"
    OTHER = "other"


class EventStatus(StrEnum):
    NEW = "new"
    DEVELOPING = "developing"
    CORRECTED = "corrected"
    REFUTED = "refuted"
    RESOLVED = "resolved"


class EvidenceStatus(StrEnum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    CONFLICTING = "conflicting"
    ABSTAINED = "abstained"


DOCUMENT_SOURCE_TYPES = frozenset(
    {
        SourceType.SEC_FILING,
        SourceType.SEC_EXHIBIT,
        SourceType.COMPANY_IR,
        SourceType.COMPANY_NEWSROOM,
        SourceType.COMPANY_EARNINGS_RELEASE,
        SourceType.PRESS_RELEASE_WIRE,
    }
)

SOURCE_TYPE_ALLOWED_TIERS = {
    SourceType.SEC_FILING: frozenset({SourceTier.REGULATORY_PRIMARY}),
    SourceType.SEC_EXHIBIT: frozenset({SourceTier.REGULATORY_PRIMARY}),
    SourceType.COMPANY_IR: frozenset({SourceTier.COMPANY_PRIMARY}),
    SourceType.COMPANY_NEWSROOM: frozenset({SourceTier.COMPANY_PRIMARY}),
    SourceType.COMPANY_EARNINGS_RELEASE: frozenset({SourceTier.COMPANY_PRIMARY}),
    SourceType.PRESS_RELEASE_WIRE: frozenset({SourceTier.COMPANY_DISTRIBUTED}),
    SourceType.MARKET_DATA: frozenset({SourceTier.MARKET_CONTEXT}),
    SourceType.SEARCH: frozenset({SourceTier.SEARCH_LEAD}),
    SourceType.SOCIAL_SENTIMENT: frozenset({SourceTier.ATTENTION_SIGNAL}),
}

DERIVED_ONLY_OUTPUT_KINDS = frozenset(
    {
        OutputKind.DOCUMENT_CHUNK,
        OutputKind.CLAIM_CANDIDATE,
        OutputKind.EVIDENCE_SPAN_CANDIDATE,
        OutputKind.CLAIM,
        OutputKind.EVIDENCE_SPAN,
        OutputKind.EVENT,
        OutputKind.EVENT_CARD,
        OutputKind.BRIEFING,
        OutputKind.INVESTIGATOR_RUN,
        OutputKind.VALIDATION_ERROR,
    }
)


def is_document_source_type(source_type: SourceType) -> bool:
    return source_type in DOCUMENT_SOURCE_TYPES


def is_valid_source_type_tier_pair(
    source_type: SourceType,
    source_tier: SourceTier,
) -> bool:
    return source_tier in SOURCE_TYPE_ALLOWED_TIERS[source_type]
