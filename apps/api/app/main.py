import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session as DBSession

from .collectors.demo import DemoCollector
from .db import Base, Session, engine
from .ingest import collect_with_retry, ingest
from .models import Ad, Creative, Observation
from .scoring import score

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
MODE = os.getenv("MODE", "demo")
if MODE not in {"demo", "live"}:
    raise RuntimeError("MODE must be demo or live")


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    if MODE == "demo":
        with Session() as session:
            ingest(session, collect_with_retry(DemoCollector()))
    yield


app = FastAPI(title="DROPSpy Radar", version="0.1.0", lifespan=lifespan)


def db():
    with Session() as session:
        yield session


def current_ads():
    return select(Ad).where(Ad.is_demo == (MODE == "demo"))


def serialize(session, ad):
    creatives = session.scalars(select(Creative).where(Creative.ad_id == ad.id)).all()
    recurrence = session.scalar(select(func.count()).select_from(Ad).where(Ad.advertiser == ad.advertiser, Ad.is_demo == ad.is_demo))
    return {c.name: getattr(ad, c.name) for c in Ad.__table__.columns} | {"creatives": [c.content for c in creatives], "score": score(ad, len(creatives), recurrence)}


@app.get("/health")
def health(session: DBSession = Depends(db)):
    session.execute(text("SELECT 1"))
    return {"status": "ok", "mode": MODE, "live_collectors": "disabled"}


@app.get("/ads")
def ads(
    q: str = "",
    country: str = "",
    platform: Literal["", "meta", "facebook", "instagram", "reels", "tiktok"] = "",
    advertiser: str = "",
    domain: str = "",
    status: Literal["", "active", "inactive", "unknown"] = "",
    detected_after: datetime | None = None,
    detected_before: datetime | None = None,
    saved: bool = False,
    sort: Literal["newest", "oldest", "advertiser"] = "newest",
    page: int = Query(1, ge=1),
    page_size: int = Query(9, ge=1, le=100),
    session: DBSession = Depends(db),
):
    stmt = current_ads()
    for column, value in [(Ad.title, q), (Ad.advertiser, advertiser), (Ad.landing_domain, domain)]:
        if value:
            stmt = stmt.where(column.icontains(value, autoescape=True))
    if country:
        stmt = stmt.where(Ad.country == country.upper())
    if platform:
        stmt = stmt.where(Ad.platform.in_(["facebook", "instagram", "reels"]) if platform == "meta" else Ad.platform == platform)
    if status:
        stmt = stmt.where(Ad.status == status)
    if detected_after:
        stmt = stmt.where(Ad.first_seen >= detected_after)
    if detected_before:
        stmt = stmt.where(Ad.first_seen <= detected_before)
    if saved:
        stmt = stmt.where(Ad.saved.is_(True))
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    ordering = {"newest": Ad.first_seen.desc(), "oldest": Ad.first_seen.asc(), "advertiser": Ad.advertiser.asc()}[sort]
    result = session.scalars(stmt.order_by(ordering, Ad.id).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [serialize(session, ad) for ad in result], "total": total, "page": page, "page_size": page_size, "mode": MODE}


def get_ad(session, ad_id):
    ad = session.scalar(current_ads().where(Ad.id == ad_id))
    if ad is None:
        raise HTTPException(404, "Ad not found")
    return ad


@app.put("/ads/{ad_id}/saved")
def save_ad(ad_id: int, saved: bool, session: DBSession = Depends(db)):
    ad = get_ad(session, ad_id)
    ad.saved = saved
    session.commit()
    return {"id": ad.id, "saved": ad.saved}


@app.get("/ads/{ad_id}/observations")
def observations(ad_id: int, session: DBSession = Depends(db)):
    get_ad(session, ad_id)
    return [
        {"observed_at": row.observed_at, "status": row.status, "source_url": row.source_url}
        for row in session.scalars(select(Observation).where(Observation.ad_id == ad_id).order_by(Observation.observed_at))
    ]


@app.get("/overview")
def overview(session: DBSession = Depends(db)):
    rows = session.scalars(current_ads()).all()
    return {
        "total_ads": len(rows),
        "advertisers": len({a.advertiser for a in rows}),
        "active_ads": sum(a.status == "active" for a in rows),
        "saved_ads": sum(a.saved for a in rows),
        "mode": MODE,
    }


@app.get("/competitors")
def competitors(session: DBSession = Depends(db)):
    rows = session.execute(
        select(Ad.advertiser, func.count(Ad.id), func.min(Ad.first_seen), func.max(Ad.last_seen))
        .where(Ad.is_demo == (MODE == "demo"))
        .group_by(Ad.advertiser)
        .order_by(func.count(Ad.id).desc())
    ).all()
    return [{"advertiser": r[0], "ad_count": r[1], "first_seen": r[2], "last_seen": r[3], "source": "demo fixture" if MODE == "demo" else "stored observations"} for r in rows]
