import hashlib
import logging
import time
from datetime import timezone
from urllib.parse import urlparse

from sqlalchemy import select

from .collectors.base import Collector
from .models import Ad, Creative, Observation

logger = logging.getLogger(__name__)


def collect_with_retry(collector: Collector, sleep=time.sleep):
    # Only transient transport failures retry. Access/validation failures fail immediately.
    for attempt in range(3):
        try:
            return collector.collect()
        except (TimeoutError, ConnectionError):
            logger.warning("collector_transient_failure attempt=%d", attempt + 1)
            if attempt == 2:
                raise
            sleep(2**attempt)


def ingest(session, records):
    for record in records:
        ad = session.scalar(select(Ad).where(Ad.platform == record.platform, Ad.source_id == record.source_id, Ad.is_demo == record.is_demo))
        first = record.first_seen.astimezone(timezone.utc).replace(tzinfo=None) if record.first_seen.tzinfo else record.first_seen
        last = record.last_seen.astimezone(timezone.utc).replace(tzinfo=None) if record.last_seen.tzinfo else record.last_seen
        if ad is None:
            ad = Ad(
                **record.model_dump(exclude={"creatives", "landing_url", "source_url", "first_seen", "last_seen"}),
                landing_url=str(record.landing_url),
                landing_domain=urlparse(str(record.landing_url)).hostname or "",
                source_url=str(record.source_url),
                first_seen=first,
                last_seen=last,
            )
            session.add(ad)
            session.flush()
        else:
            if last >= ad.last_seen:
                for key in ("status", "title", "advertiser", "country"):
                    setattr(ad, key, getattr(record, key))
                ad.landing_url = str(record.landing_url)
                ad.landing_domain = urlparse(str(record.landing_url)).hostname or ""
                ad.source_url = str(record.source_url)
            ad.first_seen = min(ad.first_seen, first)
            ad.last_seen = max(ad.last_seen, last)
        if not session.scalar(select(Observation).where(Observation.ad_id == ad.id, Observation.observed_at == last)):
            session.add(Observation(ad_id=ad.id, observed_at=last, status=record.status, source_url=str(record.source_url)))
        for content in record.creatives:
            fingerprint = hashlib.sha256(content.encode()).hexdigest()
            if not session.scalar(select(Creative).where(Creative.ad_id == ad.id, Creative.fingerprint == fingerprint)):
                session.add(Creative(ad_id=ad.id, fingerprint=fingerprint, content={"text": content, "type": "text"}))
                session.flush()
    session.commit()
    logger.info("ingest_complete records=%d", len(records))
