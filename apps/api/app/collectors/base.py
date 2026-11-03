from datetime import datetime, timezone
from typing import Literal, Protocol

from pydantic import BaseModel, HttpUrl, field_validator, model_validator


class AdRecord(BaseModel):
    source_id: str
    platform: Literal["facebook", "instagram", "reels", "tiktok"]
    advertiser: str
    title: str
    country: str
    status: Literal["active", "inactive", "unknown"]
    landing_url: HttpUrl
    source_url: HttpUrl
    first_seen: datetime
    last_seen: datetime
    is_demo: bool
    creatives: list[str]

    @field_validator("country")
    @classmethod
    def country_code(cls, value: str) -> str:
        if len(value) != 2 or not value.isalpha():
            raise ValueError("country must be a two-letter code")
        return value.upper()

    @model_validator(mode="after")
    def chronology(self):
        first = self.first_seen.astimezone(timezone.utc).replace(tzinfo=None) if self.first_seen.tzinfo else self.first_seen
        last = self.last_seen.astimezone(timezone.utc).replace(tzinfo=None) if self.last_seen.tzinfo else self.last_seen
        if last < first:
            raise ValueError("last_seen precedes first_seen")
        return self


class Collector(Protocol):
    def collect(self) -> list[AdRecord]: ...


class AccessNotConfigured(RuntimeError):
    pass
