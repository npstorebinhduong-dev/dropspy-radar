# Phase 3A acquisition harness

Read [source discovery](SOURCE_DISCOVERY_REPORT.md), [provider comparison](PROVIDER_COMPARISON.md), [rights register](DATA_ACCESS_AND_RIGHTS.md), [pilot results](US_ADS_PILOT_RESULTS.md) and [operating decision](PRODUCTION_SOURCE_RECOMMENDATION.md). **No live source is operationally verified.** This adds an isolated Python research module, not a new dashboard or a production scheduler.

## Reproduce without credentials or real data

From repository root, after the existing `bash scripts/setup.sh`:

```sh
.venv/bin/python scripts/run_acquisition_fixture.py
.venv/bin/python scripts/run_acquisition_preflights.py
(cd apps/api && ../../.venv/bin/pytest -q tests/test_acquisition.py)
```

The fixture script uses an isolated in-memory SQLite database, seeds its registry, benchmarks the synthetic file, exports/imports it via v0.2 and proves replay and DEMO isolation. It never changes the application database. The preflight script has **no transport**; its 35 outcomes are approval checks, not live runs. Artifacts under `evidence/fixture-*` contain synthetic data only. Do not change their labels to REAL.

Public documentation probe, optional and separate from ad collection:

```sh
.venv/bin/python scripts/probe_acquisition_sources.py
```

It probes the eleven fixed public URLs serially with bounded timeout/bytes, no credentials, no actor/API execution. Current result is proxy CONNECT403. Retry only after correcting/applying permitted environment settings; do not route around a denial.

## Schemas and contract

Typed models and JSON schemas: `apps/api/app/acquisition/contracts.py` and [schemas.json](schemas.json). A query supports keyword, target country, optional advertiser ID/platform and cap 1–100. Unimplemented fields (industry, objective, date windows) are rejected, never silently ignored. Source Access declares mode/corpus/approved capabilities; Query country is request intent, not independently verified reach/targeting.

Record fields are nullable source facts: ad ID, advertiser ID/name, copy/CTA, platform/aggregate meta, declared country, media/source/landing URLs, source start datetime, tri-state status, observation timestamp and raw row. No synthetic ID, date, country or status is filled in for an absent source value. URL and timestamp types are validated; source IDs are nonempty strings, not independently verified existence.

Page carries records, opaque next checkpoint, reported total, completeness and source-reported USD cost when known. Rates are fractions [0,1] over returned rows. Duplicate rate uses identified rows as denominator and `(platform, source ad ID)` identity within a source. Zero denominator → null. Counts/coverage are null if no source page was received; denied is not empty success. Timing measures harness wall time, including retries; resumed duration is accumulated active time, not downtime. Status active is source-reported at observation, never an independent current delivery guarantee.

## Adapter status

| Adapter | Implemented behavior | Missing before live |
| --- | --- | --- |
| MetaAuthorizedAdapter / OFFICIAL_API | GET Graph ads_archive, explicit API version, fields/query mapping, after cursor on pinned host | Current API version/schema/US entitlement, token, terms and registry approval |
| MetaAuthorizedAdapter / AUTHORIZED_PUBLIC_SOURCE | Bounded public HTML embedded JSON parsing, nullable fields, partial first page | Permitted automation/commercial rights, reachable page, current schema verification; no public pagination/advertiser/placement transport |
| TikTokCreativeCenterAdapter | Typed/gated disabled outcome | Documented approved automated transport; no internal endpoint implemented |
| ProviderDatasetAdapter | Existing Apify dataset GET with offset pagination, bearer header and explicit flat-column mapping | Dataset access rights, current schema, immutable query manifest, declared market/corpus; no actor execution or keyword discovery |
| FileDatasetAdapter | Bounded JSON/CSV canonical mapping, fixed dataset query manifest, pagination, fixture separation | A real permitted dataset for AUTHORIZED_IMPORT |

No official TikTok acquisition transport was implemented from unverified documentation. No provider named in the comparison has a vendor-specific actor schema integration. Configure mappings only after inspecting an authorized output sample; missing optional fields stay null. Provider nested schema transformations require a reviewed mapper, not a guessed path.

## After rights and access approval

Keep private manifests/output in ignored `acquisition.local.json` and `acquisition-output/`. Copy [sources.example.json](sources.example.json), review the rights register, and configure only the intended source. Do not put credentials in JSON. Meta/APIFY tokens come from secure process environment. Do not assume an unset token means permission is the only blocker.

Research config must say enabled + APPROVED + rights reference + supported country/filters/corpus. Existing PostgreSQL source registry must **also** be approved/live-enabled/ready with matching scope. Database policy updates are trusted operator actions; this phase does not approve any source or provide an approval-toggle UI. A saved network draft is not applied network access.

Example command, from `apps/api`, only after those prerequisites:

```sh
../../.venv/bin/python -m app.acquisition.cli \
  --config ../../acquisition.local.json --source meta-official \
  --keyword 'solar garden lights' --country US --limit 50 \
  --output ../../acquisition-output/meta-solar.json \
  --export ../../acquisition-output/meta-solar-import.json
```

CLI writes a typed error artifact and exits 2 for a denied/unsupported run. It never silently selects another source. Each pilot is serial, max ten pages, ≤100 records (duplicates included), 15-second per-request timeout, ≤2 MiB per response and three attempts for retryable GET failures. Retry-After above five seconds stops the bounded pilot instead of retrying sooner than requested. At least one second separates live pages; verified platform quotas can require stricter pacing. A 120-second deadline is checked between pages; a request already in progress remains bounded by its own timeout/retry policy, so total wall time can exceed that soft deadline. Default cap50 is recommended. Use one owner per output file; this is not a distributed scheduler.

`--resume` reuses saved records/checkpoint only with the same query, Access policy and adapter identity (file content hash/mapping or provider dataset/query/mapping). Terminal denial cannot automatically resume. Files are atomically replaced between pages. Source scope changes during a run stop collection. Checkpoints currently do not provide transactional exactly-once persistence for an interruption before writing the first response; only idempotent GETs are retried, never paid run creation.

`paid=true` always rejects execution. No actor is launched even if a budget number is set. To add a paid-run adapter, first obtain explicit budget approval and implement a reviewed **vendor-enforced cap**, idempotency, pending-run recovery and cost settlement. Existing dataset reads are allowed only after confirming permission and no paid execution effect; no such live read was performed here.

## Import into the existing dashboard

An explicit export uses v0.2 field names and preserves acquisition source/query/rights/raw/media list under `_acquisition`. It deduplicates ad ID + platform and reports skipped rows lacking required source identity/advertiser/platform/declared country. A US query does not fill a missing country.

Use **Settings → Import Data** or `/imports`: preview the exported file, review mapping, choose the correct corpus, dataset identity and rights reference, then start. Synthetic export → DEMO/demo source/demo corpus only. Actual permitted export → REAL/authorized-file and paid_ad or curated_top_ad according to evidence. Export wrapper corpus is metadata, not an automatic importer corpus override: choose it explicitly. Zero eligible rows or >2 MiB export cannot be imported; inspect/report the gap or split a permitted dataset within the existing limits. Do not fabricate required fields to pass validation.

The database registry source is file intake; original acquisition provenance appears in raw evidence. Search with matching partition, source, keyword, Meta/TikTok, US/EU and dates; open source/raw details. Existing observations handle repeated snapshots without turning partial/capped absence into inactive status. The harness never fetches creative/landing URLs.

For real manual checks, fill [manual-review.example.csv](manual-review.example.csv) with original source evidence and unknowns. `product_links` groups exact product URLs (retains query variants); it does not merge a domain into one product. `expansion` provides one-hop advertiser+keyword queries when declared, deduplicates advertisers/ads and shares the initial cap. Live expansion is unrun; scheduled monitoring and enrichment fetches remain deferred.

Research files have no automatic retention worker. Keep them out of Git and apply approved deletion periods. Structured credential redaction is defensive, not a guarantee that arbitrary free text is safe to publish.

## Validation in this task

- Full backend suite: **62 passed**, including 27 acquisition tests and all four isolated PostgreSQL migration/rollback/concurrency tests. One upstream Starlette/AnyIO deprecation warning.
- Existing production-stack Playwright: **4 passed** (seven views, JSON import/search/evidence, CSV mapping and fixture/REAL safeguards).
- Ruff, ESLint, TypeScript and production Next build passed. Docker Compose API/web/PostgreSQL healthy; both existing smoke groups passed.
- New fixture bridge measured 3 rows / 2 unique DEMO ads, preserved evidence and replay. Real records acquired: none; live query metrics remain N/A.
- GitHub remote CI is not claimed as executed. Current live-source prerequisites remain in the rights/pilot reports.
