# Public-source research — 2026-11-03

Inspected repository README, license files and collector code at the exact commits below. Commit recency is observed Git metadata, not proof that collection currently works. Upstream live scrapers were not executed. No upstream source code or fixtures were copied into DROPSpy. Names without an owner were ambiguous, so related results are listed explicitly.

## [promisingcoder/MetaAdsCollector](https://github.com/promisingcoder/MetaAdsCollector)

- Inspected commit: `46cb2215756b128ff64f2f59f7df5499c5214f57`, latest commit date: `2026-10-30T03:19:34-07:00`.
- License: MIT (LICENSE inspected).
- Data acquisition: Internal Meta GraphQL, curl_cffi browser TLS impersonation; optional browser enrichment. Not the official authorized API.
- Decision: architecture/reference research only; no code reused or collector enabled.

## [ot2dz/MetaAdsCollector](https://github.com/ot2dz/MetaAdsCollector)

- Inspected commit: `6199e30466fc08c36dbbc353b02ef3bc28f2d10c`, latest commit date: `2026-10-03T07:29:52+01:00`.
- License: MIT (LICENSE inspected).
- Data acquisition: Related fork; internal GraphQL, browser fingerprint impersonation.
- Decision: architecture/reference research only; no code reused or collector enabled.

## [2scraper/facebook-ads-scraper](https://github.com/2scraper/facebook-ads-scraper)

- Inspected commit: `57aea11dbc54c107b2a0e20d82525fa25f5b33c5`, latest commit date: `2026-11-02T23:34:46+02:00`.
- License: MIT (LICENSE inspected).
- Data acquisition: Logged-out Meta Ad Library browser engines (Playwright/Selenium/Puppeteer); optional Scraper API/CDP, proxy and 2Captcha integrations.
- Decision: architecture/reference research only; no code reused or collector enabled.

## [2scraper/tiktok-ads-scraper](https://github.com/2scraper/tiktok-ads-scraper)

- Inspected commit: `77a64a72ce02fa58beac26b29cba3a5915247e16`, latest commit date: `2026-11-02T23:40:01+02:00`.
- License: MIT (LICENSE inspected).
- Data acquisition: EU/EEA transparency library (33 regions claimed); browser-minted x-ccl-str header reused for POST search; optional CAPTCHA/proxy/CDP integrations. Does not establish US commercial ad coverage.
- Decision: architecture/reference research only; no code reused or collector enabled.

## [kalilfagundes/meta-ads-competitor-tracker](https://github.com/kalilfagundes/meta-ads-competitor-tracker)

- Inspected commit: `5443f6655141edc4532bdec4c00f25c347e91afb`, latest commit date: `2026-10-27T11:50:50-03:00`.
- License: MIT (LICENSE inspected).
- Data acquisition: Public Meta library web endpoints; optional paid Apify actor/residential proxy; FastAPI/Jinja, scheduled worker, landing-page title enrichment.
- Decision: architecture/reference research only; no code reused or collector enabled.

## [Headquarters-LLC/meta-ads-competitor-tracker-scaffold](https://github.com/Headquarters-LLC/meta-ads-competitor-tracker-scaffold)

- Inspected commit: `9989fd5c746a0e704177246e19b4ecab8b1c0007`, latest commit date: `2026-03-31T01:22:48-07:00`.
- License: No root LICENSE found; reuse not authorized by this inspection.
- Data acquisition: React/Vite UI scaffold. No verified collector or root license.
- Decision: architecture/reference research only; no code reused or collector enabled.

## Reuse and collection decision

MIT permits reuse with copyright and license notice retention; it does not grant rights to platform data or permission to circumvent access controls. Unknown-license scaffold is not a reuse candidate. Internal endpoints, minted access headers, fingerprint impersonation, proxy rotation and CAPTCHA services are not adopted by this MVP. Upstream claims of no-login availability are not independent authorization evidence.

MetaAdsCollector search returned both promisingcoder and ot2dz repositories; promisingcoder is the current README-linked project, and both snapshots were checked. The exact meta-ads-competitor-tracker match is kalilfagundes; the similarly named Headquarters scaffold is documented to avoid confusing their licenses/capabilities.

For US-first production, select an official or licensed data source with explicit commercial-ad coverage and permitted ingestion, storage and display. Verify Meta Ad Library API eligibility and geography/ad-type scope, and TikTok's authorized transparency/commercial-content API eligibility and scope with the provider before implementation. EU-library results must not be presented as US-market coverage. No provider access, official endpoint behavior, pricing, terms or freshness was validated in this task.

Only DEMO fixtures run now. Live adapters raise an explicit access-not-configured error and make no request. Future collection must stop on access denial, login wall or CAPTCHA; preserve provenance and disclose sparse or missing metrics.
