# DROPSpy Radar v0.1

A runnable DEMO-first ad intelligence workspace for the US, with an EU sample market. Next.js + TypeScript + Tailwind, FastAPI collectors, PostgreSQL, Docker Compose. All sample ads are synthetic and clearly labeled. No live scraping, CAPTCHA solving, private endpoint collection, ROAS or fabricated revenue.

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
- Normalized collector contract; fixture validation; bounded retries for transient transport exceptions; logging without credentials; platform adapters explicitly disabled until an authorized source is implemented.
- Ad identity deduplication, creative text fingerprints, first/last seen and immutable observation snapshots; demo/live separation.
- Explainable Winning Product Score with source, confidence and limitations for each input. Decorative creative cards are sample artwork, not scraped images.

## Limitations

Single-user local MVP. No live ingestion or real ad metrics. Competitor Tracker summarizes current data, without scheduled watchlists. Product Intelligence is per-ad scoring, without product clustering. Landing quality uses HTTPS syntax only. Observations show sparse snapshots, not continuous ad delivery. Schema bootstrap uses `create_all`, not migrations. One ingestion worker at a time. Authentication, migrations, real provider integration and browser UI automation are next milestones.

See [architecture and scoring](docs/architecture.md) and [source/license research](docs/research.md). Research does not establish permission to collect platform data; no code from those repositories was copied.
