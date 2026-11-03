# Validation record

Environment: 2026-11-03, Linux, Node 24.19.0, Python 3.12.14.

- `bash scripts/setup.sh`: repeated successfully with Python transitive lockfile and `npm ci`.
- `bash scripts/check.sh`: Ruff, 10 pytest tests, ESLint, TypeScript, Next.js production build, Compose configuration validation passed.
- Pytest exercises synthetic fixture validation, idempotent ingestion, observation history, stale status protection, demo/live isolation, filters/sort/pagination, saved-ad persistence, score evidence/caps, fail-closed live adapters, bounded retry and UTC normalization.
- One upstream Starlette/AnyIO deprecation warning in TestClient; tests passed.
- Container builds preserve TLS verification and use the managed system CA bundle via BuildKit secret.

See `scripts/smoke.py` for the Compose functional checks. No live platform scraper was executed. No real platform data, external landing page behavior or new-task snapshot restoration has been validated. CI workflow is provided; remote GitHub Actions execution is not claimed.

- Functional Compose smoke passed against the running PostgreSQL stack: Next.js HTML, same-origin API proxy, country/platform filtering, persistent save/unsave, observation history, score evidence, TikTok scope and advertiser summary. PostgreSQL held 12 demo ads, 33 creative records and 12 observations.
- `npm audit --omit=dev`: 0 runtime vulnerabilities in this run. Full audit reported 16 moderate dev-toolchain findings propagated from minimatch `<11.0.1` (GHSA-g3hv-75wg-m249); no high/critical findings. Suggested automatic fixes include incompatible major/downgrade changes, so no forced audit rewrite was applied. Reassess ESLint/Next lint dependency compatibility before updating this toolchain.

Active-search implementation slice (2026-11-03): 20 backend tests, Ruff, ESLint, TypeScript and Next.js production build passed. Compose PostgreSQL smoke also passed for active/span filtering, keyword matching in domains, creative analysis and explicit source-status evidence; all three services healthy. Public Meta parsing/discovery tests use synthetic HTML and mocked transport only. Actual public access failed at the environment proxy CONNECT with 403 before Facebook responded. Allowlist additions and updated start instructions are saved as a draft; no successful live collection is claimed. See docs/active-search.md for controls, opt-in flags, limitations and next verification step.
