from enum import StrEnum


class OutputKind(StrEnum):
    DOCUMENT = "document"
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
