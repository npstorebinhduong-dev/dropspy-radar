"""Original prototypes, not copied upstream. Unknown vendor schemas need explicit mapping."""
import hashlib
import json
import os
import re
from pathlib import Path

from ..collectors.meta_public import MAX_BYTES, ScriptJSON, library_url
from ..data_import import normalized_mapping, read_rows
from ..sources import require_import_source, require_live_source
from .contracts import Access, AcquisitionError, Page, Record, utcnow
from .transport import Transport


def registry_gate(session, access, query):
    access.validate_query(query)
    if access.mode in {"AUTHORIZED_IMPORT", "FIXTURE_TEST"}:
        require_import_source(session, "demo" if access.mode == "FIXTURE_TEST" else "authorized-file", "DEMO" if access.mode == "FIXTURE_TEST" else "REAL", access.corpus_type, [query.country])
    else:
        try:
            source = require_live_source(session, access.source_id, query.country, query.filters())
            if access.corpus_type not in source.corpus_types:
                raise ValueError("Unsupported corpus")
        except ValueError:
            raise AcquisitionError("registry_denied") from None


def text(value):
    return value if isinstance(value, str) and value.strip() else None


def identity(value):
    return str(value) if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).strip() else None


def parse_meta(raw, observed_at):
    snapshot = raw.get("snapshot") if isinstance(raw.get("snapshot"), dict) else {}
    body = snapshot.get("body")
    body = body.get("text") if isinstance(body, dict) else body
    bodies = raw.get("ad_creative_bodies")
    copy = "\n".join(v for v in bodies if isinstance(v, str)) if isinstance(bodies, list) else text(body)
    media = []
    for group in ("videos", "images", "cards"):
        for item in snapshot.get(group, []) or []:
            if isinstance(item, dict):
                media.extend(item[key] for key in ("video_hd_url", "video_sd_url", "original_image_url") if text(item.get(key)))
    placements = raw.get("publisher_platform") or raw.get("publisher_platforms") or []
    placement = placements[0].lower() if len(placements) == 1 and isinstance(placements[0], str) else None
    # Multiple placements stay aggregate; never guess Facebook when Instagram is unknown.
    return Record(
        ad_id=identity(raw.get("ad_archive_id") or raw.get("id")),
        advertiser_id=identity(raw.get("page_id")), advertiser=text(raw.get("page_name") or snapshot.get("page_name")),
        ad_copy=text(copy), cta=text(snapshot.get("cta_text")), platform=placement if placement in {"facebook", "instagram", "reels"} else "meta",
        country=text(raw.get("country")), media_urls=media,
        landing_url=text(snapshot.get("link_url")), source_url=text(raw.get("ad_snapshot_url") or raw.get("source_url")),
        started_at=raw.get("ad_delivery_start_time") or raw.get("start_date"),
        status="active" if raw.get("is_active") is True else "inactive" if raw.get("is_active") is False else "unknown",
        observed_at=observed_at, raw=raw,
    )


class MetaAuthorizedAdapter:
    def __init__(self, access: Access, version=None, transport=None):
        self.access = access
        self.version = version
        self.transport = transport

    def checkpoint_identity(self):
        return {"adapter": "meta", "version": self.version}

    def collect_page(self, query, checkpoint=None):
        self.access.validate_query(query)
        now = utcnow()
        if self.access.mode == "OFFICIAL_API":
            if not self.version or not re.fullmatch(r"v[0-9]+\.[0-9]+", self.version):
                raise AcquisitionError("verified_api_version_required")
            token = os.environ.get("META_ACCESS_TOKEN")
            if not token:
                raise AcquisitionError("credential_missing")
            params = {"search_terms": query.keyword, "ad_reached_countries": json.dumps([query.country]), "ad_active_status": "ACTIVE", "ad_type": "ALL", "limit": min(query.limit, 50), "fields": "id,page_id,page_name,ad_creative_bodies,ad_delivery_start_time,ad_delivery_stop_time,ad_snapshot_url,publisher_platforms"}
            if query.advertiser_id:
                params["search_page_ids"] = json.dumps([query.advertiser_id])
            if query.platform and query.platform != "meta":
                params["publisher_platforms"] = json.dumps([query.platform])
            if checkpoint:
                params["after"] = checkpoint
            transport = self.transport or Transport("graph.facebook.com")
            try:
                data = transport.get(f"https://graph.facebook.com/{self.version}/ads_archive", params, {"Authorization": f"Bearer {token}"})
            finally:
                if not self.transport:
                    transport.close()
            if not isinstance(data, dict) or not isinstance(data.get("data"), list) or data.get("error"):
                raise AcquisitionError("upstream_schema_error")
            paging = data.get("paging") or {}
            after = (paging.get("cursors") or {}).get("after") if paging.get("next") else None
            # Never follow a returned next URL (may include credentials); use opaque after on pinned host.
            return Page(records=[parse_meta(row, now) for row in data["data"]], next_checkpoint=after, completeness="partial")
        if self.access.mode != "AUTHORIZED_PUBLIC_SOURCE":
            raise AcquisitionError("adapter_mode_mismatch")
        if checkpoint or query.advertiser_id or query.platform:
            raise AcquisitionError("public_first_page_only")
        transport = self.transport or Transport("www.facebook.com")
        try:
            html = transport.get(library_url(query.keyword, query.country), text=True)
        finally:
            if not self.transport:
                transport.close()
        if len(html.encode()) > MAX_BYTES:
            raise AcquisitionError("response_too_large")
        lower = html.lower()
        if any(marker in lower for marker in ("/checkpoint/", 'id="captcha', 'id="login_form', "<title>log in", "<title>just a moment")):
            raise AcquisitionError("access_challenge")
        parser = ScriptJSON()
        parser.feed(html)
        stack, rows, visited, recognized = list(parser.payloads), [], 0, False
        while stack:
            node = stack.pop()
            visited += 1
            if visited > 50000:
                raise AcquisitionError("parse_limit")
            if isinstance(node, dict):
                if isinstance(node.get("collated_results"), list):
                    rows.extend(node["collated_results"])
                    recognized = True
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
            elif isinstance(node, list):
                stack.extend(v for v in node if isinstance(v, (dict, list)))
        if not recognized:
            raise AcquisitionError("unsupported_public_schema")
        records = [parse_meta(row, now) for row in rows if isinstance(row, dict) and row.get("is_active") is True]
        return Page(records=records[:query.limit], completeness="capped" if len(records) > query.limit else "partial")


class TikTokCreativeCenterAdapter:
    """No documented approved automated transport established; never calls internal endpoints."""
    def __init__(self, access):
        self.access = access

    def collect_page(self, query, checkpoint=None):
        self.access.validate_query(query)
        raise AcquisitionError("needs_approved_creative_center_transport")


class ProviderDatasetAdapter:
    """Read an existing authorized Apify dataset; never launch/poll/retry a paid actor.

    Dataset query provenance must match this benchmark. This is NOT keyword discovery.
    """
    def __init__(self, access, dataset_id, dataset_query, mapping, transport=None):
        self.access, self.dataset_query, self.mapping = access, dataset_query, mapping
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", dataset_id):
            raise AcquisitionError("invalid_dataset_id")
        self.dataset_id, self.transport = dataset_id, transport

    def checkpoint_identity(self):
        return {"adapter": "provider_dataset", "dataset_id": self.dataset_id, "dataset_query": self.dataset_query.model_dump(), "mapping": self.mapping}

    def collect_page(self, query, checkpoint=None):
        self.access.validate_query(query)
        if self.access.mode != "LICENSED_PROVIDER":
            raise AcquisitionError("adapter_mode_mismatch")
        if query.model_dump(exclude={"limit"}) != self.dataset_query.model_dump(exclude={"limit"}):
            raise AcquisitionError("dataset_query_mismatch")
        token = os.environ.get("APIFY_TOKEN")
        if not token:
            raise AcquisitionError("credential_missing")
        offset = int(checkpoint or "0")
        if offset < 0:
            raise AcquisitionError("invalid_checkpoint")
        transport = self.transport or Transport("api.apify.com")
        try:
            data = transport.get(f"https://api.apify.com/v2/datasets/{self.dataset_id}/items", {"offset": offset, "limit": min(50, query.limit), "format": "json"}, {"Authorization": f"Bearer {token}"})
        finally:
            if not self.transport:
                transport.close()
        if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
            raise AcquisitionError("upstream_schema_error")
        records = []
        for raw in data:
            if str(raw.get("fixture_only", "")).lower() == "true" or str(raw.get("is_demo", "")).lower() == "true":
                raise AcquisitionError("fixture_partition_mismatch")
            values = {target: raw.get(column) for target, column in self.mapping.items() if raw.get(column) is not None}
            # Observation of dataset retrieval is known; country/placement/status remain source facts.
            values.update(observed_at=utcnow(), raw=raw)
            records.append(Record.model_validate(values))
        return Page(records=records, next_checkpoint=str(offset + len(data)) if len(data) == min(50, query.limit) else None, completeness="partial")


class FileDatasetAdapter:
    def __init__(self, access, filename, mapping=None, dataset_query=None):
        self.access, self.filename = access, Path(filename)
        self.mapping, self.dataset_query = mapping or {}, dataset_query

    def checkpoint_identity(self):
        if self.filename.is_file() and self.filename.stat().st_size <= MAX_BYTES:
            sha = hashlib.sha256(self.filename.read_bytes()).hexdigest()
        else:
            sha = None
        return {"adapter": "file", "file_sha256": sha, "filename": str(self.filename), "mapping": self.mapping, "dataset_query": self.dataset_query.model_dump() if self.dataset_query else None}

    def collect_page(self, query, checkpoint=None):
        self.access.validate_query(query)
        if self.access.mode not in {"FIXTURE_TEST", "AUTHORIZED_IMPORT"}:
            raise AcquisitionError("adapter_mode_mismatch")
        if self.dataset_query is None or query.model_dump(exclude={"limit"}) != self.dataset_query.model_dump(exclude={"limit"}):
            raise AcquisitionError("dataset_query_manifest_required")
        if self.filename.stat().st_size > MAX_BYTES:
            raise AcquisitionError("file_too_large")
        rows, fixture, _ = read_rows(self.filename.read_bytes(), self.filename.name)
        if fixture != (self.access.mode == "FIXTURE_TEST"):
            raise AcquisitionError("fixture_partition_mismatch")
        mapping, _ = normalized_mapping(rows, self.mapping)
        start = int(checkpoint or "0")
        if start < 0 or start > len(rows):
            raise AcquisitionError("invalid_checkpoint")
        output = []
        for row in rows[start:start + min(25, query.limit)]:
            values = {key: row.get(column) for key, column in mapping.items()}
            aliases = {"external_id": "ad_id", "title": "ad_copy", "creative_text": "ad_copy", "creative_url": "media_urls", "delivery_start": "started_at"}
            clean = {}
            for key, value in values.items():
                target = aliases.get(key, key)
                if target in Record.model_fields and value not in (None, ""):
                    clean[target] = [value] if key == "creative_url" else value
            if "observed_at" not in clean:
                raise AcquisitionError("observation_timestamp_missing")
            clean["raw"] = row
            output.append(Record.model_validate(clean))
        end = start + len(output)
        return Page(records=output, next_checkpoint=str(end) if end < len(rows) else None, source_reported_total=len(rows), completeness="partial")
