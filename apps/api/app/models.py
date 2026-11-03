from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Ad(Base):
    __tablename__ = "ads"
    __table_args__ = (UniqueConstraint("platform", "source_id", "is_demo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(30), index=True)
    advertiser: Mapped[str] = mapped_column(String(200), index=True)
    title: Mapped[str] = mapped_column(String(500))
    country: Mapped[str] = mapped_column(String(2), index=True)
    status: Mapped[str] = mapped_column(String(20))
    landing_url: Mapped[str] = mapped_column(String(2000))
    landing_domain: Mapped[str] = mapped_column(String(255), index=True)
    source_url: Mapped[str] = mapped_column(String(2000))
    first_seen: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)
    is_demo: Mapped[bool] = mapped_column(Boolean, index=True)
    saved: Mapped[bool] = mapped_column(Boolean, default=False)


class Creative(Base):
    __tablename__ = "creatives"
    __table_args__ = (UniqueConstraint("ad_id", "fingerprint"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_id: Mapped[int] = mapped_column(ForeignKey("ads.id", ondelete="CASCADE"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSON)


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (UniqueConstraint("ad_id", "observed_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_id: Mapped[int] = mapped_column(ForeignKey("ads.id", ondelete="CASCADE"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20))
    source_url: Mapped[str] = mapped_column(String(2000))
