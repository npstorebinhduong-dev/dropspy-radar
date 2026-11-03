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
    registry_source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), index=True)
    advertiser_ref_id: Mapped[int | None] = mapped_column(ForeignKey("advertisers.id"))
    external_id: Mapped[str | None] = mapped_column(String(150))
    corpus: Mapped[str] = mapped_column(String(40), default="unknown", server_default="unknown")
    delivery_start: Mapped[datetime | None] = mapped_column(DateTime)
    delivery_end: Mapped[datetime | None] = mapped_column(DateTime)


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


class AdProvenance(Base):
    """Additive import metadata; v0.1 ad/creative/observation tables remain compatible."""

    __tablename__ = "ad_provenance"
    ad_id: Mapped[int] = mapped_column(ForeignKey("ads.id", ondelete="CASCADE"), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(80))
    external_id: Mapped[str] = mapped_column(String(100))
    rights_reference: Mapped[str] = mapped_column(String(500))
    imported_at: Mapped[datetime] = mapped_column(DateTime)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(40))
    corpus_types: Mapped[list] = mapped_column(JSON)
    countries: Mapped[list] = mapped_column(JSON)
    supported_filters: Mapped[list] = mapped_column(JSON)
    approval_status: Mapped[str] = mapped_column(String(40))
    rights_reference: Mapped[str] = mapped_column(String(1000))
    live_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    import_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    media_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_days: Mapped[int | None]
    state: Mapped[str] = mapped_column(String(30))


class Advertiser(Base):
    __tablename__ = "advertisers"
    __table_args__ = (UniqueConstraint("source_id", "identity_key", "is_demo", name="uq_advertiser_identity"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    identity_key: Mapped[str] = mapped_column(String(200))
    external_id: Mapped[str | None] = mapped_column(String(150))
    name: Mapped[str] = mapped_column(String(200))
    identity_method: Mapped[str] = mapped_column(String(30))
    is_demo: Mapped[bool] = mapped_column(Boolean)


class CollectionQuery(Base):
    __tablename__ = "collection_queries"
    __table_args__ = (UniqueConstraint("source_id", "scope_hash", name="uq_query_scope"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    scope_hash: Mapped[str] = mapped_column(String(64))
    parameters: Mapped[dict] = mapped_column(JSON)


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    query_id: Mapped[str] = mapped_column(ForeignKey("collection_queries.id"))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    completeness: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30))
    record_count: Mapped[int] = mapped_column(default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str] = mapped_column(String(500), default="Absence never implies inactivity")


class ImportJob(Base):
    __tablename__ = "import_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    dataset_id: Mapped[str] = mapped_column(String(60))
    filename: Mapped[str] = mapped_column(String(200))
    file_sha256: Mapped[str] = mapped_column(String(64))
    file_format: Mapped[str] = mapped_column(String(10))
    data_label: Mapped[str] = mapped_column(String(10))
    corpus: Mapped[str] = mapped_column(String(40))
    rights_reference: Mapped[str] = mapped_column(String(1000))
    mapping: Mapped[dict] = mapped_column(JSON)
    raw_rows: Mapped[list] = mapped_column(JSON)
    normalized_rows: Mapped[list] = mapped_column(JSON)
    errors: Mapped[list] = mapped_column(JSON)
    total_rows: Mapped[int]
    error_count: Mapped[int]
    processed: Mapped[int] = mapped_column(default=0)
    cursor: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(30), index=True)
    completeness: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("collection_runs.id"))


class RawEvidence(Base):
    __tablename__ = "raw_evidence"
    __table_args__ = (UniqueConstraint("job_id", "row_number", name="uq_evidence_row"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("import_jobs.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("collection_runs.id"))
    ad_id: Mapped[int] = mapped_column(ForeignKey("ads.id"), index=True)
    observation_id: Mapped[int] = mapped_column(ForeignKey("observations.id"))
    row_number: Mapped[int]
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime)
    source_url: Mapped[str | None] = mapped_column(String(2000))
    raw_sha256: Mapped[str] = mapped_column(String(64))
    raw_data: Mapped[dict] = mapped_column(JSON)
    normalized_data: Mapped[dict] = mapped_column(JSON)
    rights_reference: Mapped[str] = mapped_column(String(1000))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime)
    is_demo: Mapped[bool] = mapped_column(Boolean)
