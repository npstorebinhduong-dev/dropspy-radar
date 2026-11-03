"""Bounded CSV/JSON previews and durable, idempotent PostgreSQL batch import.
Uploaded data is parsed only. No URL is fetched and no spreadsheet formula evaluated.
"""

import csv
import hashlib
import io
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import PurePath
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, field_validator, model_validator
from sqlalchemy import delete, select, update

from .db import Session
from .ingest import naive_utc, upsert_ad
from .models import Advertiser, CollectionQuery, CollectionRun, ImportJob, RawEvidence, Source, Observation
from .sources import insert_for, require_import_source

logger = logging.getLogger(__name__)
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 2000
BATCH_SIZE = 50
FIELDS = [
    "external_id",
    "platform",
    "advertiser",
    "advertiser_id",
    "title",
    "country",
    "status",
    "observed_at",
    "first_seen",
    "delivery_start",
    "delivery_end",
    "source_url",
    "landing_url",
    "creative_text",
    "creative_url",
]
ALIASES = {
    "external_id": ["external_id", "ad_id", "source_id", "ad_archive_id"],
    "advertiser": ["advertiser", "advertiser_name", "page_name"],
    "observed_at": ["observed_at", "last_seen"],
    "creative_text": ["creative_text", "body", "ad_copy", "creatives"],
}


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class ImportOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_id: str = "authorized-file"
    dataset_id: str = Field(default="my-dataset", pattern=r"^[a-z][a-z0-9_-]{0,49}$")
    data_label: Literal["REAL", "DEMO"] = "REAL"
    corpus: Literal["paid_ad", "curated_top_ad", "unknown", "demo"] = "paid_ad"
    rights_reference: str = Field(default="", max_length=1000)
    permission_attested: bool = False
    completeness: Literal["complete", "partial", "capped"] = "partial"
    mapping: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def rights(self):
        if self.data_label == "REAL" and (not self.permission_attested or len(self.rights_reference.strip()) < 10):
            raise ValueError("REAL import requires permission attestation and a meaningful rights reference")
        if any(key not in FIELDS for key in self.mapping):
            raise ValueError("Unknown mapping target field")
        return self


class ImportRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    external_id: str = Field(min_length=1, max_length=150)
    platform: Literal["meta", "facebook", "instagram", "reels", "tiktok"]
    advertiser: str = Field(min_length=1, max_length=200)
    advertiser_id: str | None = Field(default=None, max_length=150)
    title: str = Field(default="", max_length=500)
    country: str = Field(pattern="^[A-Z]{2}$")
    status: Literal["active", "inactive", "unknown"] = "unknown"
    observed_at: datetime
    first_seen: datetime | None = None
    delivery_start: datetime | None = None
    delivery_end: datetime | None = None
    source_url: HttpUrl | None = None
    landing_url: HttpUrl | None = None
    creative_text: str = Field(default="", max_length=20000)
    creative_url: HttpUrl | None = None

    @field_validator("country", mode="before")
    @classmethod
    def country_code(cls, value):
        return value.upper() if isinstance(value, str) else value

    @field_validator("platform", "status", mode="before")
    @classmethod
    def lower_enum(cls, value):
        return value.lower() if isinstance(value, str) else value

    @field_validator("observed_at", "first_seen", "delivery_start", "delivery_end")
    @classmethod
    def utc(cls, value):
        return naive_utc(value) if value else None

    @field_validator("source_url", "landing_url", "creative_url")
    @classmethod
    def no_credentials(cls, value):
        if value and (value.username or value.password):
            raise ValueError("URLs with credentials are not accepted")
        return value

    @model_validator(mode="after")
    def chronology(self):
        if self.observed_at > now_utc() + timedelta(minutes=5):
            raise ValueError("Observation is in the future")
        if self.first_seen and self.first_seen > self.observed_at:
            raise ValueError("first_seen is after observed_at")
        if self.delivery_start and self.delivery_end and self.delivery_end < self.delivery_start:
            raise ValueError("delivery_end is before delivery_start")
        return self


def read_rows(payload, filename):
    if len(payload) > MAX_BYTES:
        raise ValueError("File exceeds 2 MiB")
    suffix = PurePath(filename).suffix.lower()
    if suffix not in {".json", ".csv"}:
        raise ValueError("Only .json and .csv files are supported")
    try:
        text = payload.decode("utf-8-sig")
        fixture = False
        if suffix == ".json":
            obj = json.loads(text)
            fixture = isinstance(obj, dict) and obj.get("fixture_only") is True
            rows = obj.get("records") if isinstance(obj, dict) else obj
        else:
            reader = csv.DictReader(io.StringIO(text, newline=""))
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError("CSV needs unique column names")
            rows = []
            for row in reader:
                if None in row:
                    raise ValueError("CSV row has more cells than headers")
                rows.append(row)
                if len(rows) > MAX_ROWS:
                    raise ValueError("File exceeds 2000 rows")
        if not isinstance(rows, list) or not rows or len(rows) > MAX_ROWS or not all(isinstance(row, dict) for row in rows):
            raise ValueError("Expected 1–2000 objects in records or JSON array")
        if any(len(row) > 100 for row in rows):
            raise ValueError("At most 100 columns per record")
        fixture = fixture or any(str(row.get("fixture_only", "")).lower() == "true" or row.get("is_demo") is True or str(row.get("is_demo", "")).lower() == "true" for row in rows)
        return rows, fixture, suffix[1:]
    except (UnicodeError, json.JSONDecodeError, csv.Error, RecursionError):
        raise ValueError("Invalid UTF-8, JSON or CSV data") from None


def normalized_mapping(rows, supplied):
    headers = sorted({key for row in rows for key in row})
    lower = {h.lower(): h for h in headers}
    mapping = {}
    for target in FIELDS:
        if target in supplied:
            if supplied[target] and supplied[target] not in headers:
                raise ValueError(f"Mapping column not found: {target}")
            if supplied[target]:
                mapping[target] = supplied[target]
        else:
            for alias in ALIASES.get(target, [target]):
                if alias.lower() in lower:
                    mapping[target] = lower[alias.lower()]
                    break
    return mapping, headers


def create_preview(session, payload, filename, options):
    source = require_import_source(session, options.source_id, options.data_label, options.corpus)
    rows, fixture, fmt = read_rows(payload, filename)
    if fixture and options.data_label != "DEMO":
        raise ValueError("Test/demo fixtures may only be imported as DEMO")
    mapping, headers = normalized_mapping(rows, options.mapping)
    valid, errors = [], []
    for number, raw in enumerate(rows, 1):
        values = {target: raw.get(column) for target, column in mapping.items()}
        for key in list(values):
            if values[key] == "" or values[key] is None:
                values.pop(key)
        if isinstance(values.get("creative_text"), list):
            texts = values["creative_text"]
            if not all(isinstance(t, str) for t in texts):
                errors.append({"row": number, "field": "creative_text", "message": "Expected text strings"})
                continue
            values["creative_text"] = "\n".join(texts)
        try:
            record = ImportRecord.model_validate(values)
            require_import_source(session, source.id, options.data_label, options.corpus, [record.country])
            valid.append({"row_number": number, "record": record.model_dump(mode="json")})
        except ValidationError as exc:
            errors.append({"row": number, "field": ".".join(str(p) for p in exc.errors()[0]["loc"]), "message": exc.errors()[0]["msg"]})
        except ValueError as exc:
            errors.append({"row": number, "field": "country", "message": str(exc)})
    sha = hashlib.sha256(payload).hexdigest()
    identity = digest({"file": sha, "options": options.model_dump(exclude={"mapping"}), "mapping": mapping})
    job_id = str(uuid.uuid4())
    created = now_utc()
    values = dict(
        id=job_id,
        idempotency_key=identity,
        source_id=source.id,
        dataset_id=options.dataset_id,
        filename=PurePath(filename).name[:200],
        file_sha256=sha,
        file_format=fmt,
        data_label=options.data_label,
        corpus=options.corpus,
        rights_reference=options.rights_reference,
        mapping=mapping,
        raw_rows=rows,
        normalized_rows=valid,
        errors=errors,
        total_rows=len(rows),
        error_count=len(errors),
        processed=0,
        cursor=0,
        status="preview",
        completeness=options.completeness,
        created_at=created,
        expires_at=created + timedelta(minutes=30),
        lease_until=None,
        run_id=None,
    )
    session.execute(insert_for(session, ImportJob).values(**values).on_conflict_do_nothing(index_elements=["idempotency_key"]))
    session.commit()
    job = session.scalar(select(ImportJob).where(ImportJob.idempotency_key == identity))
    if job.status in {"preview", "expired"} and job.expires_at < created:
        job.status, job.expires_at = "preview", created + timedelta(minutes=30)
        job.raw_rows, job.normalized_rows, job.errors = rows, valid, errors
        job.processed, job.cursor = 0, 0
        session.commit()
    return job_summary(job, preview=True) | {"headers": headers, "fields": FIELDS}


def job_summary(job, preview=False):
    result = {
        key: getattr(job, key)
        for key in [
            "id",
            "source_id",
            "dataset_id",
            "filename",
            "file_sha256",
            "file_format",
            "data_label",
            "corpus",
            "rights_reference",
            "mapping",
            "total_rows",
            "error_count",
            "processed",
            "cursor",
            "status",
            "completeness",
            "created_at",
            "expires_at",
            "run_id",
        ]
    }
    result["valid_rows"] = job.total_rows - job.error_count
    result["errors"] = job.errors[:100]
    result["progress"] = round(100 * job.processed / job.total_rows) if job.total_rows else 0
    if preview:
        result["sample"] = job.normalized_rows[:5]
    return result


def start_import(session, job_id):
    job = session.get(ImportJob, job_id)
    if not job:
        raise LookupError("Import not found")
    require_import_source(session, job.source_id, job.data_label, job.corpus)
    if job.status == "preview":
        if job.expires_at < now_utc():
            raise ValueError("Preview expired; create a new preview with a new dataset ID or mapping")
        if not job.normalized_rows:
            raise ValueError("No valid rows to import")
        session.execute(update(ImportJob).where(ImportJob.id == job_id, ImportJob.status == "preview").values(status="queued"))
        session.commit()
        session.refresh(job)
    return job_summary(job)


def store_row(session, job, entry):
    record = ImportRecord.model_validate(entry["record"])
    source = require_import_source(session, job.source_id, job.data_label, job.corpus, [record.country])
    is_demo = job.data_label == "DEMO"
    advertiser_key = digest([job.dataset_id, record.platform, "id" if record.advertiser_id else "name", record.advertiser_id or record.advertiser])
    stmt = insert_for(session, Advertiser).values(
        source_id=source.id,
        identity_key=advertiser_key,
        external_id=record.advertiser_id,
        name=record.advertiser,
        identity_method="source_id" if record.advertiser_id else "exact_name",
        is_demo=is_demo,
    )
    adv_id = session.scalar(stmt.on_conflict_do_update(index_elements=["source_id", "identity_key", "is_demo"], set_={"name": stmt.excluded.name}).returning(Advertiser.id))
    identity = "core:" + digest([source.id, job.dataset_id, record.external_id])
    values = dict(
        source_id=identity,
        external_id=record.external_id,
        platform=record.platform,
        advertiser=record.advertiser,
        title=record.title,
        country=record.country,
        status=record.status,
        landing_url=str(record.landing_url or ""),
        source_url=str(record.source_url or ""),
        landing_domain=urlparse(str(record.landing_url or "")).hostname or "",
        first_seen=record.first_seen or record.observed_at,
        last_seen=record.observed_at,
        is_demo=is_demo,
        registry_source_id=source.id,
        advertiser_ref_id=adv_id,
        corpus=job.corpus,
        delivery_start=record.delivery_start,
        delivery_end=record.delivery_end,
    )
    creative = {"text": record.creative_text, "type": "text", "media_url": str(record.creative_url) if record.creative_url else None}
    ad_id = upsert_ad(session, values, [creative] if record.creative_text or record.creative_url else [])
    raw = job.raw_rows[entry["row_number"] - 1]
    until = now_utc() + timedelta(days=source.retention_days) if source.retention_days else None
    session.execute(
        insert_for(session, RawEvidence)
        .values(
            job_id=job.id,
            run_id=job.run_id,
            ad_id=ad_id,
            observation_id=session.scalar(select(Observation.id).where(Observation.ad_id == ad_id, Observation.observed_at == record.observed_at)),
            row_number=entry["row_number"],
            source_id=source.id,
            observed_at=record.observed_at,
            source_url=str(record.source_url) if record.source_url else None,
            raw_sha256=digest(raw),
            raw_data=raw,
            normalized_data=entry["record"],
            rights_reference=job.rights_reference,
            retention_until=until,
            is_demo=is_demo,
        )
        .on_conflict_do_nothing(index_elements=["job_id", "row_number"])
    )


def process_job(job_id, factory=Session, stop=None):
    """Claim once; each batch commits data and cursor atomically. Expired leases requeue."""
    with factory() as session:
        claimed = session.execute(
            update(ImportJob)
            .where(ImportJob.id == job_id, ImportJob.status == "queued")
            .values(status="running", lease_until=now_utc() + timedelta(minutes=5))
            .returning(ImportJob.id)
        ).scalar()
        if not claimed:
            session.rollback()
            return
        job = session.get(ImportJob, job_id)
        if not job.run_id:
            scope = {"dataset_id": job.dataset_id, "corpus": job.corpus, "data_label": job.data_label}
            scope_hash = digest(scope)
            query_id = str(uuid.uuid4())
            session.execute(
                insert_for(session, CollectionQuery)
                .values(id=query_id, source_id=job.source_id, scope_hash=scope_hash, parameters=scope)
                .on_conflict_do_nothing(index_elements=["source_id", "scope_hash"])
            )
            query_id = session.scalar(select(CollectionQuery.id).where(CollectionQuery.source_id == job.source_id, CollectionQuery.scope_hash == scope_hash))
            job.run_id = str(uuid.uuid4())
            session.add(
                CollectionRun(
                    id=job.run_id,
                    query_id=query_id,
                    source_id=job.source_id,
                    started_at=now_utc(),
                    finished_at=None,
                    completeness="partial" if job.error_count else job.completeness,
                    status="running",
                    record_count=0,
                    is_demo=job.data_label == "DEMO",
                )
            )
        session.commit()
    try:
        while not stop or not stop.is_set():
            with factory() as session:
                job = session.get(ImportJob, job_id)
                require_import_source(session, job.source_id, job.data_label, job.corpus)
                batch = job.normalized_rows[job.cursor : job.cursor + BATCH_SIZE]
                for entry in batch:
                    store_row(session, job, entry)
                job.cursor += len(batch)
                job.processed = job.cursor + job.error_count
                job.lease_until = now_utc() + timedelta(minutes=5)
                run = session.get(CollectionRun, job.run_id)
                run.record_count = job.cursor
                if job.cursor == len(job.normalized_rows):
                    job.status = "completed_with_errors" if job.error_count else "completed"
                    job.lease_until = None
                    run.status = job.status
                    run.finished_at = now_utc()
                session.commit()
                if job.status in {"completed", "completed_with_errors"}:
                    return
        with factory() as session:
            session.execute(update(ImportJob).where(ImportJob.id == job_id, ImportJob.status == "running").values(status="queued", lease_until=None))
            session.commit()
    except Exception as exc:
        logger.error("import_failed job_id=%s error_type=%s", job_id, type(exc).__name__)
        with factory() as session:
            job = session.get(ImportJob, job_id)
            job.status = "failed"
            job.errors = [
                *job.errors,
                {"row": None, "field": "batch", "message": "Batch failed; committed batches are preserved. Retry after reviewing the error.", "error_type": type(exc).__name__},
            ]
            job.lease_until = None
            if job.run_id:
                run = session.get(CollectionRun, job.run_id)
                run.status = "failed"
                run.completeness = "partial"
                run.finished_at = now_utc()
            session.commit()


def purge_expired(session):
    current = now_utc()
    session.execute(delete(RawEvidence).where(RawEvidence.retention_until.is_not(None), RawEvidence.retention_until <= current))
    for job in session.scalars(select(ImportJob).where(ImportJob.status.in_(["preview", "expired", "completed", "completed_with_errors", "failed"]))):
        source = session.get(Source, job.source_id)
        expired_preview = job.status in {"preview", "expired"} and job.expires_at < current
        expired_raw = source.retention_days is not None and job.created_at + timedelta(days=source.retention_days) < current
        if expired_preview or expired_raw:
            job.raw_rows, job.normalized_rows = [], []
            if expired_preview:
                job.status = "expired"
    session.commit()


def worker_loop(stop):
    last_purge = 0.0
    while not stop.is_set():
        try:
            with Session() as session:
                if time.monotonic() - last_purge > 60:
                    purge_expired(session)
                    last_purge = time.monotonic()
                session.execute(update(ImportJob).where(ImportJob.status == "running", ImportJob.lease_until < now_utc()).values(status="queued"))
                session.commit()
                job_id = session.scalar(select(ImportJob.id).where(ImportJob.status == "queued").order_by(ImportJob.created_at).limit(1))
            if job_id:
                process_job(job_id, stop=stop)
            else:
                stop.wait(1)
        except Exception:
            logger.exception("import_worker_iteration_failed")
            stop.wait(2)


def start_worker():
    stop = threading.Event()
    thread = threading.Thread(target=worker_loop, args=(stop,), name="import-worker", daemon=True)
    thread.start()
    return stop, thread
