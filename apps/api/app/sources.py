"""Registry declares capabilities and operator approval separately from availability."""

from sqlalchemy import select

from .models import Source

EU_COUNTRIES = ["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"]
MARKETS = ["US", *EU_COUNTRIES]
FILTERS = ["keyword", "country", "platform", "advertiser", "date", "status", "domain"]


def source_definitions():
    def source(id, name, kind, corpus, countries, approval="pending", imported=False, state="unverified"):
        return dict(
            id=id,
            name=name,
            kind=kind,
            corpus_types=corpus,
            countries=countries,
            supported_filters=FILTERS,
            approval_status=approval,
            rights_reference="Operator attestation required per file" if imported else "Source approval and current terms not verified",
            live_enabled=False,
            import_enabled=imported,
            media_storage_allowed=False,
            retention_days=30 if imported else None,
            state=state,
        )

    definitions = [
        source("meta-ad-library", "Meta Ads Library", "public_or_official", ["paid_ad"], MARKETS),
        source("tiktok-ad-library", "TikTok Ad Library", "official_api", ["paid_ad"], EU_COUNTRIES),
        source("tiktok-creative-center", "TikTok Creative Center", "curated_library", ["curated_top_ad"], MARKETS),
        source("authorized-file", "Authorized File Import", "authorized_file", ["paid_ad", "curated_top_ad", "unknown"], MARKETS, "operator_attested", True, "ready"),
        source("licensed-provider", "Licensed Data Provider", "licensed_provider", ["paid_ad"], [], state="not_configured"),
        source("demo", "Demo Data", "demo", ["demo"], MARKETS, "demo_only", True, "ready"),
        source("legacy-unknown", "Legacy data: provenance unknown", "unknown", ["unknown"], [], state="disabled"),
    ]

    for item in definitions:
        if item["id"] == "meta-ad-library":
            item["supported_filters"] = ["keyword", "country", "status"]
        elif item["id"] == "tiktok-ad-library":
            item["supported_filters"] = ["keyword", "country", "advertiser", "date"]
        elif item["id"] == "tiktok-creative-center":
            item["supported_filters"] = ["keyword", "country"]
        elif item["id"] in {"licensed-provider", "legacy-unknown"}:
            item["supported_filters"] = []
    return definitions


def insert_for(session, model):
    if session.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert(model)


def seed_sources(session):
    for data in source_definitions():
        session.execute(insert_for(session, Source).values(**data).on_conflict_do_nothing(index_elements=["id"]))
    session.flush()


def require_import_source(session, source_id, label, corpus, countries=()):
    source = session.get(Source, source_id)
    if source is None or not source.import_enabled or source.state != "ready":
        raise ValueError("Source is not enabled for file import")
    if (label == "DEMO") != (source.id == "demo"):
        raise ValueError("DEMO must use Demo Data; real files must use an authorized non-demo source")
    if label == "REAL" and source.approval_status not in {"approved", "operator_attested"}:
        raise ValueError("Source approval is required")
    if corpus not in source.corpus_types:
        raise ValueError("Unsupported corpus for this source")
    if any(c not in source.countries for c in countries):
        raise ValueError("Unsupported country for this source")
    return source


def require_live_source(session, source_id, country, filters):
    source = session.get(Source, source_id)
    if source is None or source.approval_status != "approved" or not source.live_enabled or source.state != "ready":
        raise ValueError("Live collection blocked: explicit source approval and activation required")
    if country not in source.countries or any(f not in source.supported_filters for f in filters):
        raise ValueError("Unsupported source country or filter")
    return source


def list_sources(session):
    return [{c.name: getattr(s, c.name) for c in Source.__table__.columns} for s in session.scalars(select(Source).order_by(Source.name))]
