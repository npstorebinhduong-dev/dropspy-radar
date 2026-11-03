# Active ad search & creative analysis — implementation slice

This slice follows the Phase 2 audit and prioritizes finding source-reported active ads and understanding their creative. It does not implement the entire Phase 2 roadmap or the proposed product opportunity score.

## Search and analysis

Dashboard defaults to `status=active`. Keyword search covers title, stored creative text, advertiser and landing domain. Country/platform/advertiser/domain/detected-date filters still apply. New controls: last observed within 3/7/30 days, minimum observation span, recently observed / longest span / most creative texts sorting. The API keeps its previous default (all statuses) for compatibility.

`GET /ads/{id}/analysis` returns deterministic English rules for convenience, urgency, social proof, problem/solution, discount, shipping, guarantee and CTA. Every hit includes a literal excerpt, character offsets, creative index, rule version and confidence. It also shows observation count/span, distinct stored texts, same-name advertiser count, source details and limitations. It does not fetch landing pages or run an LLM. ROAS, sales and revenue remain null. The v0.1 score is labeled a research signal score, not a validated product outcome score.

`status_evidence` separates the reported status from freshness and independent verification. An old active observation stays source-reported active with a stale warning; it is not silently promoted to current delivery or changed to inactive. DEMO is always labeled and never mixed with real search.

## Public Meta page reader

Public Facebook Ad Library is the first direct discovery path. No paid provider or API token is required by this code path. Use only where public-page access and intended use are permitted by the source. Public visibility and operator opt-in do not grant blanket data/media rights.

From the repository root, after reviewing `.env` settings:

```sh
MODE=live ENABLE_META_PUBLIC_COLLECTION=1 docker compose up -d --wait
# Managed cloud builds use compose.cloud.yaml as described in README.
```

Both environment flags are required. This changes the visible partition to real observations; existing DEMO records remain in the database. Defaults remain DEMO and collection off.

Open Meta Ads Search, enter a keyword and country, then choose **Read public results**. **Open public library** opens the normal source search for manual research, including while DEMO is enabled. The button never presents stored/demo results as freshly collected data.

`POST /discovery/meta` accepts `{"q":"portable blender","country":"US"}`. One normal GET to the fixed `https://www.facebook.com/ads/library/` search page, timeout 20s, max response 2 MiB, no redirects, 30-second local cooldown and one in-process collection at a time. Only embedded `application/json` search rows with `collated_results` are recognized. No GraphQL request, token extraction, supplied cookies, browser execution, fingerprint spoofing, CAPTCHA handling, proxy rotation, or fallback to restricted paths is implemented. Platform access challenges and unsupported JavaScript-only pages fail explicitly, not as zero successful results. Unrecognized HTML does not activate another transport.

Partial support: first embedded page only, active rows only; no exhaustive pagination. Source-reported placements, media URLs and delivery dates are preserved as separate metadata; first_seen/last_seen are local observation times. Rows missing a genuine landing URL/title/advertiser are skipped and counted because the v0.1 schema requires them. Media links are displayed, never downloaded/archived by this reader. No global market coverage or current-delivery verification is claimed.

The in-memory cooldown is appropriate for one local API process only. Authentication, shared rate limiting, durable job leases and full source/run/field-level provenance are prerequisites before public/multi-worker deployment.

## Observed environment blocker

On 2026-11-03, a normal GET to the public Meta library failed at the environment proxy with **Tunnel connection failed: 403 Forbidden**, before a Facebook response was obtained. Thus no conclusion about Facebook-side access or live parser compatibility is supported.

A network draft was saved adding `facebook.com` and `www.facebook.com`, preserving `api.github.com` and package-manager presets. Draft saving does not apply policy. Review/save the settings and publish the environment through the environment UI, then retry the actual source request. Even with networking restored, the public page may require JavaScript/login/challenge or change shape; this reader will stop and report that limitation. Do not call this live discovery ready until a permitted real response has been tested.

## Authorized file fallback (local CLI)

No public upload endpoint is added. In `apps/api`, run with the same PostgreSQL DATABASE_URL as the API:

```sh
../../.venv/bin/python -m app.import_ads /path/to/authorized-dataset.json
# In Compose, stream a local file to an internal temporary file, then run the CLI:
docker compose exec -T api sh -c 'cat > /tmp/authorized-dataset.json && python -m app.import_ads /tmp/authorized-dataset.json' < /path/to/authorized-dataset.json
```

The Compose command must be run from the repository root (the first command is from apps/api). Dataset wrapper fields: `source_id` (lowercase slug), `kind=authorized_file`, `corpus=paid_ad`, meaningful `rights_reference`, `permission_attested=true`, and `records` (1–1000). Attestation is the operator's declaration, not independent permission verification. Only import datasets you actually have permission to use; synthetic fixtures remain DEMO.

Each record follows `AdRecord` in `apps/api/app/collectors/base.py`: external `source_id` (1–100 characters, no colon), platform, advertiser, title, country, active/inactive/unknown status, genuine landing/source URLs, first_seen/last_seen observation timestamps, `is_demo=false`, and text creatives. Do not substitute delivery start for first observation. Files are capped at 1 MiB; future observations and demo relabeling are rejected. IDs are namespaced per source to avoid provider collision. Commit/rollback is atomic for the local batch, with replay preserving existing ad identity and observations. Concurrency-safe import upserts are deferred; run one ingestion at a time.

The additive `ad_provenance` table keeps source ID, original external ID, operator rights reference and import timestamp; public reads also keep source details. Existing v0.1 tables are untouched. This is an additive bootstrap, not the complete Alembic/source-run schema from the blueprint. The metadata is ad-level, not immutable per-field/per-run rights history; migration/provenance expansion remains follow-up work.

## Validation

20 backend tests pass, including original v0.1 tests plus active/text search, literal wildcard handling, span/sort filters, rules with exact text offsets, stale-status behavior, import gate/namespacing/replay, fail-closed login/challenge/shell detection and a mocked live discovery roundtrip. All public-reader tests use synthetic HTML/mocks; no upstream code is run. ESLint, TypeScript and Next.js production build pass. PostgreSQL functional checks are run against Compose separately; live platform success is not claimed.
