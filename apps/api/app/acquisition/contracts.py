from datetime import datetime, timezone
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

Mode = Literal["OFFICIAL_API", "LICENSED_PROVIDER", "AUTHORIZED_PUBLIC_SOURCE", "AUTHORIZED_IMPORT", "FIXTURE_TEST"]
Corpus = Literal["paid_ad", "curated_top_ad", "unknown", "demo"]


def utcnow():
    return datetime.now(timezone.utc)


class AcquisitionError(RuntimeError):
    def __init__(self, kind):
        super().__init__(kind)
        self.kind = kind


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keyword: str = Field(min_length=1, max_length=200)
    country: str = Field(default="US", pattern="^[A-Z]{2}$")
    advertiser_id: str | None = Field(default=None, max_length=150)
    platform: Literal["meta", "facebook", "instagram", "reels", "tiktok"] | None = None
    limit: int = Field(default=50, ge=1, le=100)

    def filters(self):
        return {"keyword", "country"} | ({"advertiser"} if self.advertiser_id else set()) | ({"platform"} if self.platform else set())


class Access(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    source_name: str
    mode: Mode
    corpus_type: Corpus
    enabled: bool = False
    authorization_status: Literal["NEEDS_APPROVAL", "APPROVED", "DENIED", "FIXTURE_ONLY"] = "NEEDS_APPROVAL"
    rights_reference: str = ""
    countries: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    paid: bool = False
    budget_approved: bool = False
    hard_budget_usd: float = Field(default=0, ge=0, allow_inf_nan=False)

    def validate_query(self, query):
        if self.mode == "FIXTURE_TEST":
            if self.authorization_status != "FIXTURE_ONLY" or self.corpus_type != "demo":
                raise AcquisitionError("fixture_partition_required")
        elif not self.enabled or self.authorization_status != "APPROVED" or len(self.rights_reference.strip()) < 10:
            raise AcquisitionError("needs_approval")
        if query.country not in self.countries:
            raise AcquisitionError("unsupported_country")
        if not query.filters().issubset(self.filters):
            raise AcquisitionError("unsupported_filter")
        # Paid job creation is intentionally absent. A local cap alone cannot cap vendor spend.
        if self.paid:
            raise AcquisitionError("paid_execution_disabled_requires_vendor_enforced_budget")


class Record(BaseModel):
    """Nullable source facts; query geography/placement never fills absent source fields."""
    model_config = ConfigDict(extra="forbid")
    ad_id: str | None = None
    advertiser_id: str | None = None
    advertiser: str | None = None
    ad_copy: str | None = None
    cta: str | None = None
    platform: Literal["meta", "facebook", "instagram", "reels", "tiktok"] | None = None
    country: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    media_urls: list[HttpUrl] = Field(default_factory=list)
    landing_url: HttpUrl | None = None
    source_url: HttpUrl | None = None
    started_at: datetime | None = None
    status: Literal["active", "inactive", "unknown"] = "unknown"
    observed_at: datetime
    raw: dict = Field(default_factory=dict)

    @field_validator("observed_at", "started_at")
    @classmethod
    def timezone_required(cls, value):
        if value and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @field_validator("ad_id", "advertiser_id")
    @classmethod
    def source_identity(cls, value):
        if value is not None and (not value.strip() or len(value) > 150):
            raise ValueError("Source identity must be 1–150 characters")
        return value

    @field_validator("media_urls", "landing_url", "source_url")
    @classmethod
    def no_credential_urls(cls, value):
        for url in value if isinstance(value, list) else [value]:
            if url and (url.username or url.password):
                raise ValueError("Credential-bearing URLs prohibited")
        return value


class Page(BaseModel):
    records: list[Record]
    next_checkpoint: str | None = None
    source_reported_total: int | None = Field(default=None, ge=0)
    completeness: Literal["complete", "partial", "capped"] = "partial"
    actual_cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    currency: Literal["USD"] | None = None


class Adapter(Protocol):
    access: Access

    def collect_page(self, query: Query, checkpoint: str | None) -> Page: ...
