# DROPSpy Radar v0.2 — importing permitted ad data

Use the existing checkout; do not create a new project. PostgreSQL is the supported migration/runtime database. The original seven dashboard views and APIs remain, with source/partition controls added. No new AI model or Winning Product Score was introduced.

## Run

```sh
bash scripts/setup.sh
docker compose up --build -d --wait
# Managed cloud proxy + CA:
docker compose -f compose.yaml -f compose.cloud.yaml up --build -d --wait
```

Startup applies Alembic under a PostgreSQL advisory lock, adopts the existing v0.1 tables, adds the data-core schema and starts the import worker. It does not delete or reset the database. Run only one Compose mutation at a time. Keep loopback bindings and database volume. The app is a trusted single-workspace development app, not an authenticated multi-tenant deployment; do not expose it publicly without access control.

API defaults remain compatible with MODE (`demo` by default). Dashboard can independently select DEMO or REAL/UNKNOWN through `data_mode`, without mixing results. The saved-ad, observation, analysis and evidence calls carry the same partition. REAL means operator-attested data origin, not independent verification of ad activity, revenue, licensing or market coverage. Legacy records lacking registry evidence are UNKNOWN. Source-reported active status is still timestamped and can be stale.

## Dashboard upload workflow

1. Open **Settings → Import Data**, or the `/imports` page. Source cards and import history also have dedicated `/data-sources` and `/import-history` pages.
2. Select REAL with Authorized File Import for data you may use, or DEMO with Demo Data for tests. REAL requires a permission attestation and rights/license reference. Give the dataset a stable lowercase ID; reuse it for subsequent snapshots of that dataset. Use a different dataset ID for unrelated external ID namespaces.
3. Choose corpus (`paid_ad`, `curated_top_ad` or `unknown` for real files; `demo` for fixtures) and completeness (`partial`, `capped`, `complete for declared scope`). None of these choices permits inactivity inference from absence.
4. Upload UTF-8 CSV or JSON: max 2 MiB / 2,000 objects / 100 columns. No archives, remote URL imports, executable scripts or spreadsheet evaluation. Browser and server validate; the server enforces limits independently.
5. Select **Preview file**. Review valid/error counts, first five normalized rows and row-level errors. No ad is ingested yet. Auto-mapping recognizes canonical names and common aliases; use the mapping dropdowns to map your actual columns. **Revalidate mapping** creates/reuses a preview for the canonical mapping. Changing mappings disables Import until validated again.
6. Select **Import valid rows** explicitly. Invalid rows are not ingested, remain in the report and force the run to partial. Progress is persisted and polled in Import History. Each batch transaction writes ads, advertiser/creative identities, observations, raw evidence and cursor together.
7. Open Details/errors, download the full JSON error report, retry remaining rows after a diagnosed failure, or choose **Search imported ads** after completion. Search supports Meta/TikTok, US/EU27, keyword (copy/title/advertiser/domain), dates, source and reported status. Source URLs, source-delivery dates and raw records appear in ad detail. Missing optional URLs are not invented or fetched.

Exact duplicate previews use a unique content/options/mapping fingerprint and reuse one job. Ads use source + stable dataset + platform + external ID identity. PostgreSQL `ON CONFLICT` resolves concurrent ad/creative/advertiser/observation writes. Reimporting a later snapshot updates last_seen/status only when newer and preserves earliest observation and Saved Ads. Media URL identity is exact, not perceptual similarity.

## Input shape

JSON can be an array of records or `{ "records": [...] }`. CSV needs unique headers. Unmapped extra fields remain in raw evidence. Required normalized fields:

| Field | Meaning |
| --- | --- |
| external_id | Source ad ID, string 1–150 characters; aliases ad_id/source_id/ad_archive_id |
| platform | meta (placement unspecified), facebook, instagram, reels, tiktok; lowercase normalized |
| advertiser | Source advertiser name, ≤200 characters; advertiser_name/page_name aliases |
| country | Two-letter US or EU27 country supported by source; case normalized; declared market, not independently verified targeting |
| observed_at | Actual observation timestamp; last_seen alias; naive timestamps interpreted as UTC |

Optional: advertiser_id, title (≤500), status active/inactive/unknown (default unknown), first_seen observation timestamp, delivery_start/end source-supplied dates, source_url, landing_url, creative_text (body/ad_copy/creatives aliases), creative_url. Dates remain separate: delivery_start is not used as first observation. Only HTTP(S) URLs without embedded credentials are accepted; null URLs remain missing. Creative text may be text or a list of text strings. A single unknown value does not become zero or verified active.

Fixture files under `apps/api/tests/fixtures/` are synthetic and marked fixture_only. Import them only as DEMO. Complete/partial/capped JSON histories and a custom-header CSV are provided for test/evaluation. Removing a marker does not grant rights to relabel synthetic data; the operator is responsible for truthful dataset provenance.

## APIs

- `GET /v1/sources`: source ID/kind/corpus/countries/filters/approval/state/media/raw-retention policy.
- `POST /v1/imports/preview`: multipart `file` + JSON `options`; returns preview ID, mappings, headers, sample, counts/errors.
- `POST /v1/imports/{id}/start`: explicitly queue valid rows; repeated start is safe.
- `GET /v1/imports?page=1&page_size=20` and `GET /v1/imports/{id}`: persisted status/progress and first 100 error details.
- `POST /v1/imports/{id}/retry`: failed job with retained data only; resumes committed cursor and preserves run ID.
- Existing `/ads`, `/overview`, `/competitors`, `/ads/{id}/saved`, `/ads/{id}/observations`, `/ads/{id}/analysis` remain. `data_mode=demo|real` selects one partition; `/ads` adds `market=US|EU` and `source=...`.
- `GET /ads/{id}/evidence?data_mode=...&page=1`: raw/normalized rows, checksums, source/run/observation IDs, rights reference and retention deadline; paginated ten rows.

Options: source_id, dataset_id, data_label, corpus, rights_reference, permission_attested, completeness and mapping (normalized field → original header). DEMO options must use source_id=demo and corpus=demo. Other source imports require enabled import capabilities and supported market/corpus. Pending live sources cannot be used as a way to bypass the import gate.

## Persistence, expiry and recovery

Tables: sources, collection_queries, collection_runs, advertisers, ads, creatives, observations, raw_evidence, import_jobs; legacy ad_provenance retained for compatibility. Raw evidence links to canonical observations and each import run. Fields retain original row and normalized representation plus SHA-256, rights reference and observed time.

Preview expires after 30 minutes. Re-uploading the same expired preview renews it from the newly supplied file. Worker purges expired raw evidence and retained row copies according to the source raw-retention policy (currently 30 days for file/demo), approximately once a minute. Ad projections and job summary/counts remain. Raw evidence APIs hide expired records immediately. Dataset-specific shorter retention/legal requirements must be reviewed before import; current single-source policy is configurable through trusted DB administration, not an unverified UI approval toggle.

Jobs are claimed atomically; a five-minute lease allows recovery if a worker dies. Cursor and records commit together per 50-row batch; clean shutdown requeues unfinished jobs, process failure preserves committed batches. Full process kill can wait until the lease expires. Failed batches remain visible and can be retried after diagnosis. No stopped-ad inference is performed even for complete files, so partial/capped absence cannot create false inactive ads.

## Migrations and tests

```sh
cd apps/api
../../.venv/bin/alembic upgrade head
# Rollback ONLY in a disposable test DB; this removes v0.2 provenance/jobs.
../../.venv/bin/alembic downgrade 0001_legacy
```

Migration 0001 freezes/adopts v0.1. Migration 0002 adds core schema and labels pre-existing synthetic rows DEMO, older non-demo rows UNKNOWN. Test rollback in disposable schemas only. Back up the database before operational downgrades. SQLite is for isolated unit tests/fresh local demos; upgrading old SQLite files is not the PostgreSQL migration workflow.

```sh
bash scripts/check.sh
# On an isolated PostgreSQL database; each test creates/drops only a unique test schema:
cd apps/api
TEST_DATABASE_URL=postgresql+psycopg://... ../../.venv/bin/pytest -q
# From apps/web with the application stack running:
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e
```

If Chromium is not preinstalled, use `npx playwright install --with-deps chromium` in a permitted test environment and omit the executable override. `TEST_DATABASE_URL` must point to a test database where schema creation is allowed, not production. CI starts a dedicated PostgreSQL service for these tests. Browser fixtures only import DEMO records; they never seed fake REAL ads.
