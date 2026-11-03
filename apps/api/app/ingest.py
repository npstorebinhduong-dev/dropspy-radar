import hashlib
import logging
import time
from datetime import timezone
from urllib.parse import urlparse

from sqlalchemy import case

from .collectors.base import Collector
from .models import Ad, Creative, Observation
from .sources import insert_for

logger = logging.getLogger(__name__)


def collect_with_retry(collector: Collector, sleep=time.sleep):
    for attempt in range(3):
        try:
            return collector.collect()
        except (TimeoutError, ConnectionError):
            logger.warning("collector_transient_failure attempt=%d", attempt + 1)
            if attempt == 2:
                raise
            sleep(2**attempt)


def naive_utc(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def upsert_ad(session, values, creatives):
    """Unique constraint + ON CONFLICT serializes competing writers on PostgreSQL."""
    stmt = insert_for(session, Ad).values(**values)
    incoming = stmt.excluded
    newer = incoming.last_seen >= Ad.last_seen
    changes = {
        key: case((newer, getattr(incoming, key)), else_=getattr(Ad, key)) for key in values if key not in {"source_id", "platform", "is_demo", "saved", "first_seen", "last_seen"}
    }
    changes["first_seen"] = case((incoming.first_seen < Ad.first_seen, incoming.first_seen), else_=Ad.first_seen)
    changes["last_seen"] = case((incoming.last_seen > Ad.last_seen, incoming.last_seen), else_=Ad.last_seen)
    ad_id = session.scalar(stmt.on_conflict_do_update(index_elements=["platform", "source_id", "is_demo"], set_=changes).returning(Ad.id))
    session.execute(
        insert_for(session, Observation)
        .values(ad_id=ad_id, observed_at=values["last_seen"], status=values["status"], source_url=values["source_url"])
        .on_conflict_do_nothing(index_elements=["ad_id", "observed_at"])
    )
    for content in creatives:
        data = content if isinstance(content, dict) else {"text": content, "type": "text"}
        import json

        # Preserve the v0.1 text identity so upgrading an existing DB does not duplicate its creatives.
        fingerprint_input = data["text"] if set(data) <= {"text", "type", "media_url"} and not data.get("media_url") else json.dumps(data, sort_keys=True, ensure_ascii=False)
        fingerprint = hashlib.sha256(fingerprint_input.encode()).hexdigest()
        session.execute(insert_for(session, Creative).values(ad_id=ad_id, fingerprint=fingerprint, content=data).on_conflict_do_nothing(index_elements=["ad_id", "fingerprint"]))
    session.expire_all()
    return ad_id


def ingest(session, records, *, commit=True):
    for record in records:
        values = record.model_dump(exclude={"creatives", "landing_url", "source_url", "first_seen", "last_seen"})
        values.update(
            landing_url=str(record.landing_url),
            landing_domain=urlparse(str(record.landing_url)).hostname or "",
            source_url=str(record.source_url),
            first_seen=naive_utc(record.first_seen),
            last_seen=naive_utc(record.last_seen),
        )
        # Legacy callers remain isolated; only a synthetic fixture has known provenance.
        values.update(registry_source_id="demo" if record.is_demo else "legacy-unknown", corpus="demo" if record.is_demo else "unknown")
        upsert_ad(session, values, record.creatives)
    if commit:
        session.commit()
    else:
        session.flush()
    logger.info("ingest_complete records=%d", len(records))
