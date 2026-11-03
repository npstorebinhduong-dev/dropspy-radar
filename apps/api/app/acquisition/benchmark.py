import hashlib
import json
import logging
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import ValidationError

from .contracts import AcquisitionError, Query, Record, utcnow

logger = logging.getLogger(__name__)
SECRET_KEYS = {"token", "accesstoken", "authorization", "cookie", "password", "secret", "apikey", "clientsecret"}


def sensitive_key(value):
    return value.lower().replace("_", "").replace("-", "") in SECRET_KEYS


def safe_value(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if sensitive_key(key) else safe_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [safe_value(item) for item in value]
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        try:
            url = urlsplit(value)
            if url.username or url.password:
                return "[REDACTED URL]"
            query = [(key, "[REDACTED]" if sensitive_key(key) else item) for key, item in parse_qsl(url.query, keep_blank_values=True)]
            return urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), url.fragment))
        except ValueError:
            return "[INVALID URL]"
    return value


def fingerprint(access, query, adapter_identity=None):
    value = {"access": access.model_dump(), "query": query.model_dump(), "version": "acquisition-0.1", "adapter_identity": adapter_identity}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def write_artifact(path, artifact):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(safe_value(artifact), ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def summarize(artifact):
    rows = artifact["records"]
    measured = artifact["pages_received"] > 0
    unique = {(r["platform"], r["ad_id"]) for r in rows if r["ad_id"]}
    with_id = sum(bool(r["ad_id"]) for r in rows)
    result = {key: artifact[key] for key in ("query", "target_country", "source_name", "source_id", "mode", "corpus_type", "authorization_status", "observed_at", "source_reported_total", "duration_ms", "actual_cost", "error_type", "completeness", "next_checkpoint", "pages_received")}
    result.update(
        returned_count=len(rows) if measured else None,
        unique_ad_count=len(unique) if measured else None,
        duplicate_rate=(with_id - len(unique)) / with_id if with_id else None,
        observed_country_coverage=sum(bool(r["country"]) for r in rows) / len(rows) if rows else None,
        actual_cost_basis="source_reported_USD" if artifact["actual_cost"] is not None else "unknown; no source charge reported",
        synthetic=artifact["mode"] == "FIXTURE_TEST",
    )
    for metric, field in {"valid_ad_id_rate": "ad_id", "advertiser_id_coverage": "advertiser_id", "ad_copy_coverage": "ad_copy", "media_url_coverage": "media_urls", "landing_url_coverage": "landing_url", "started_at_coverage": "started_at"}.items():
        result[metric] = sum(bool(r[field]) for r in rows) / len(rows) if rows else None
    return result


def benchmark(adapter, query, path, gate=None, resume=False, max_pages=10, deadline_seconds=120):
    """Single source/query, serial, at most 100 records incl duplicates. No fallback."""
    start = time.monotonic()
    access = adapter.access
    scope = fingerprint(access, query, adapter.checkpoint_identity() if hasattr(adapter, "checkpoint_identity") else type(adapter).__name__)
    artifact = {"version": "acquisition-0.1", "scope_hash": scope, "query": query.keyword, "query_spec": query.model_dump(), "target_country": query.country, "source_name": access.source_name, "source_id": access.source_id, "mode": access.mode, "corpus_type": access.corpus_type, "authorization_status": access.authorization_status, "rights_reference": access.rights_reference, "observed_at": utcnow().isoformat(), "records": [], "pages_received": 0, "source_reported_total": None, "duration_ms": 0, "actual_cost": None, "error_type": None, "completeness": "partial", "next_checkpoint": None, "seen_checkpoints": []}
    if resume:
        old = json.loads(Path(path).read_text())
        if old["scope_hash"] != scope:
            raise AcquisitionError("checkpoint_scope_mismatch")
        # Terminal denial requires a fresh reviewed run, never an automatic retry.
        if old["error_type"] in {"access_denied", "access_challenge", "registry_denied", "needs_approval", "proxy_or_network_denied"}:
            raise AcquisitionError("terminal_run_cannot_resume")
        if not old["next_checkpoint"]:
            raise AcquisitionError("no_checkpoint_to_resume")
        artifact = old
        artifact["error_type"] = None
    previous_duration = artifact["duration_ms"]
    checkpoint = artifact["next_checkpoint"]
    costs = []
    cost_known = artifact["pages_received"] == 0 or artifact["actual_cost"] is not None
    if artifact["actual_cost"] is not None:
        costs.append(artifact["actual_cost"])
    try:
        access.validate_query(query)
        if access.mode not in {"FIXTURE_TEST", "AUTHORIZED_IMPORT"} and gate is None:
            raise AcquisitionError("registry_gate_required")
        for _ in range(max_pages):
            if fingerprint(access, query, adapter.checkpoint_identity() if hasattr(adapter, "checkpoint_identity") else type(adapter).__name__) != scope:
                raise AcquisitionError("source_scope_changed_during_run")
            if gate:
                gate(access, query)
            if time.monotonic() - start >= deadline_seconds:
                raise AcquisitionError("pilot_deadline")
            if artifact["pages_received"] and access.mode not in {"FIXTURE_TEST", "AUTHORIZED_IMPORT"}:
                time.sleep(1)
            remaining = query.limit - len(artifact["records"])
            if remaining <= 0:
                artifact["completeness"] = "capped"
                break
            page = adapter.collect_page(query.model_copy(update={"limit": remaining}), checkpoint)
            if len(page.records) > remaining:
                # Never advance a cursor after dropping rows (that would skip on resume).
                raise AcquisitionError("source_exceeded_requested_limit")
            artifact["records"].extend(record.model_dump(mode="json") for record in page.records)
            artifact["pages_received"] += 1
            artifact["source_reported_total"] = page.source_reported_total if page.source_reported_total is not None else artifact["source_reported_total"]
            if page.actual_cost is None or page.currency != "USD":
                cost_known = False
            else:
                costs.append(page.actual_cost)
            artifact["actual_cost"] = sum(costs) if cost_known else None
            artifact["completeness"] = page.completeness
            checkpoint = page.next_checkpoint
            artifact["next_checkpoint"] = checkpoint
            artifact["duration_ms"] = previous_duration + round((time.monotonic() - start) * 1000)
            write_artifact(path, artifact)
            logger.info(json.dumps({"event": "acquisition_page", "source_id": access.source_id, "mode": access.mode, "records": len(page.records), "pages": artifact["pages_received"]}))
            if not checkpoint:
                break
            if checkpoint in artifact["seen_checkpoints"]:
                raise AcquisitionError("repeated_checkpoint")
            artifact["seen_checkpoints"].append(checkpoint)
        else:
            artifact["completeness"] = "capped"
        if len(artifact["records"]) >= query.limit:
            artifact["completeness"] = "capped"
    except (AcquisitionError, ValidationError, ValueError, TypeError, KeyError) as exc:
        artifact["error_type"] = exc.kind if isinstance(exc, AcquisitionError) else "schema_error"
        artifact["completeness"] = "partial"
        if artifact["error_type"] in {"access_denied", "access_challenge", "registry_denied"}:
            artifact["authorization_status"] = "DENIED"
    artifact["duration_ms"] = previous_duration + round((time.monotonic() - start) * 1000)
    artifact["summary"] = summarize(artifact)
    write_artifact(path, artifact)
    return artifact


def export_import(artifact):
    """Explicit file bridge; original acquisition provenance survives in raw evidence."""
    synthetic = artifact["mode"] == "FIXTURE_TEST"
    if not synthetic and artifact["authorization_status"] != "APPROVED":
        raise AcquisitionError("export_not_authorized")
    rows, skipped, seen = [], [], set()
    for index, value in enumerate(artifact["records"]):
        record = Record.model_validate(value)
        identity = (record.platform, record.ad_id)
        if not all((record.ad_id, record.platform, record.advertiser, record.country)):
            skipped.append({"index": index, "reason": "missing_import_identity_or_declared_country"})
            continue
        if identity in seen:
            continue
        seen.add(identity)
        rows.append({"external_id": record.ad_id, "platform": record.platform, "advertiser": record.advertiser, "advertiser_id": record.advertiser_id, "country": record.country, "observed_at": record.observed_at.isoformat(), "status": record.status, "title": (record.ad_copy or "")[:500], "creative_text": record.ad_copy, "creative_url": str(record.media_urls[0]) if record.media_urls else None, "landing_url": str(record.landing_url) if record.landing_url else None, "source_url": str(record.source_url) if record.source_url else None, "delivery_start": record.started_at.isoformat() if record.started_at else None, "_acquisition": {"source_id": artifact["source_id"], "source_name": artifact["source_name"], "mode": artifact["mode"], "corpus_type": artifact["corpus_type"], "query_spec": artifact["query_spec"], "rights_reference": artifact["rights_reference"], "scope_hash": artifact["scope_hash"], "completeness": artifact["completeness"], "media_urls": record.model_dump(mode="json")["media_urls"], "raw": record.raw}, "fixture_only": synthetic})
    return safe_value({"fixture_only": synthetic, "corpus_type": artifact["corpus_type"], "records": rows, "skipped": skipped})


def expansion(adapter, query, initial, path_prefix, gate=None, max_advertisers=3):
    """One serial, bounded advertiser hop, shares remaining original record budget."""
    if "advertiser" not in adapter.access.filters:
        return {"status": "unsupported", "additional_unique_ads": None, "runs": []}
    seen = {(r["platform"], r["ad_id"]) for r in initial["records"] if r["ad_id"]}
    ids = sorted({r["advertiser_id"] for r in initial["records"] if r["advertiser_id"]})[:max_advertisers]
    additional, runs = 0, []
    remaining = max(0, query.limit - len(initial["records"]))
    for number, advertiser in enumerate(ids):
        if remaining == 0:
            break
        child = Query(**(query.model_dump() | {"advertiser_id": advertiser, "limit": remaining}))
        result = benchmark(adapter, child, f"{path_prefix}-{number}.json", gate)
        remaining -= len(result["records"])
        for row in result["records"]:
            key = (row["platform"], row["ad_id"])
            if row["ad_id"] and key not in seen:
                additional += 1
                seen.add(key)
        runs.append(result["summary"])
        if result["error_type"]:
            break
    measured = any(run["pages_received"] for run in runs)
    return {"status": "partial" if measured and any(run["error_type"] for run in runs) else "measured" if measured else "blocked" if runs else "unrun_no_budget_or_advertiser_ids", "synthetic": adapter.access.mode == "FIXTURE_TEST", "additional_unique_ads": additional if measured else None, "runs": runs}


def product_links(records):
    """Exact URL grouping, never domain-as-product; query/variant parameters retained."""
    groups = {}
    for row in records:
        if not row.get("landing_url"):
            continue
        url = urlsplit(str(row["landing_url"]))
        key = urlunsplit((url.scheme, url.netloc, url.path, url.query, ""))
        groups.setdefault(key, {"domain": url.hostname, "product_url": key, "ad_ids": []})["ad_ids"].append(row.get("ad_id"))
    return list(groups.values())
