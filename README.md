# DROPSpy Radar v0.2

A runnable DEMO-first ad intelligence workspace for the US, with an EU sample market. Next.js + TypeScript + Tailwind, FastAPI collectors, PostgreSQL, Docker Compose. Default sample ads are synthetic and clearly labeled. An opt-in public Meta first-page reader and authorized local-file import are available; live access is not yet verified in this environment. No CAPTCHA solving, private endpoint collection, ROAS or fabricated revenue.

## Quick start

Requires Docker Engine + Compose v2. Copy `.env.example` to `.env` if customization is needed; defaults run DEMO without secrets.

```sh
docker compose up --build -d
curl --fail http://127.0.0.1:8000/health
curl --fail 'http://127.0.0.1:8000/ads?country=US&platform=meta&page_size=2'
```

Dashboard listens on port 3000; API on 8000; API documentation at `/docs` on the API. Database is internal to Compose. Ports bind to loopback. Sample database credentials are local development defaults; changing POSTGRES variables also requires updating DATABASE_URL. Do not deploy publicly without authentication and proper secrets.

Managed cloud (proxy CA retained, TLS verification enabled):

```sh
docker compose -f compose.yaml -f compose.cloud.yaml up --build -d
```

## Development

Requires Node.js 24, npm 11, Python 3.12. Use the existing checkout in each isolated cloud task; no worktree is needed.

```sh
bash scripts/setup.sh
docker compose up db -d
# Forward the internal db port only if running the API on the host, or use SQLite:
cd apps/api
MODE=demo DATABASE_URL=sqlite:///./dropspy.db ../../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
# separate shell, from repository root:
npm --prefix apps/web run dev
```

Next.js proxies `/api/*` to API_URL (default host development: API port 8000). A production web build embeds API_URL; rebuild to change it. Compose uses `http://api:8000`.

```sh
bash scripts/check.sh
# PostgreSQL integration smoke against running Compose:
.venv/bin/python scripts/smoke.py
```

Dependency versions: Python requirements.lock pins transitive dependencies, npm package-lock committed and installed with `npm ci`. Stop only this project's services with `docker compose down` (add `-v` only when deliberately deleting demo data).

## MVP features

- Overview counts from the database; Meta search (Facebook/Instagram/Reels), TikTok search, product signal details, advertiser summary, persistent Saved Ads, settings status.
- Keyword/title, country, platform, advertiser, landing domain, status, first-detected date filters; stable sort and pagination. Meta search's platform scope is all Meta placements.
- Normalized collector contract; fixture validation; bounded retries for transient transport exceptions; logging without credentials; baseline platform adapters disabled; separate public Meta reader requires explicit operator opt-in and stops on access gates.
- Ad identity deduplication, creative text fingerprints, first/last seen and immutable observation snapshots; demo/live separation.
- Explainable Winning Product Score with source, confidence and limitations for each input. Decorative creative cards are sample artwork, not scraped images.

## Limitations

Single-user local MVP. Public Meta collection is opt-in, partial and currently blocked by environment networking; no successful live ad retrieval is claimed. Competitor Tracker summarizes current data, without scheduled watchlists. Product Intelligence is per-ad scoring, without product clustering. Landing quality uses HTTPS syntax only. Observations show sparse snapshots, not continuous ad delivery. PostgreSQL startup uses Alembic migrations; imports use atomic upserts and a durable, leased batch worker. Authentication, approved live providers and advanced product intelligence remain future milestones.

See [architecture and scoring](docs/architecture.md) and [source/license research](docs/research.md). Research does not establish permission to collect platform data; no code from those repositories was copied.

See [active search, analysis and public Meta access](docs/active-search.md) for new controls, configuration, observed network blocker and import format. The Phase 2 score remains proposed; v0.2 implements the migration and import-job foundation described below.

## v0.2 Data Foundation

Keep the seven dashboard views; Settings now contains Data Sources, upload/preview/mapping, and persisted Import History. Dedicated pages are also available at `/data-sources`, `/imports`, `/import-history`. Select DEMO or REAL/UNKNOWN in search, then filter Meta/TikTok, US/EU27, source, advertiser, text and dates. Detail shows raw evidence and provenance. REAL is operator-attested, not an independent data/license verification.

[Import guide, schema, migrations and tests](docs/import-guide.md) · [US live-source feasibility](docs/research/US_LIVE_SOURCE_FEASIBILITY.md).

Upload/import never fetches external URLs or evaluates CSV formulas. Exact replay and concurrent upserts are tested on PostgreSQL. Synthetic complete/partial/capped histories remain DEMO; absence never marks an ad stopped. Source registry approval is mandatory before live collection, in addition to environment flags. No new AI or Winning Product Score is implemented.

## Phase 3A acquisition research

[Adapter/benchmark run guide](docs/acquisition/README.md) · [source discovery](docs/acquisition/SOURCE_DISCOVERY_REPORT.md) · [pilot results](docs/acquisition/US_ADS_PILOT_RESULTS.md). Live sources remain disabled pending verified access/rights; runnable fixture benchmarks exercise the existing v0.2 intake path without claiming real inventory.

[Phase 3B network recheck and first-real-source outcome](docs/acquisition/PHASE3B_FIRST_REAL_SOURCE.md): actual applied-policy/proxy evidence and remaining blocker; no live collection success claimed.
