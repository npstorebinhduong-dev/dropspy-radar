# Data access and rights register

2026-11-03 UTC. No platform/provider approval or current commercial data license has been verified for this workspace. Runtime source credentials/outbound identities are absent. **None of the live sources is commercially cleared by this research.** The report is an engineering evidence register, not a grant of rights.

| Source | Endpoint exists | Workspace approval | Credential readiness | US commercial corpus | Commercial analysis/display rights | Media archive | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Meta public Library | Public URL known; current response blocked | None recorded | Public page may not require token; permitted automation unresolved | U | U — automated collection terms request blocked | U / disabled | NEEDS_APPROVAL |
| Meta official | Historical official Graph client evidence | None recorded | META_ACCESS_TOKEN absent | U; endpoint existence ≠ entitlement | U | U / disabled | NEEDS_APPROVAL |
| TikTok Creative Center | Public URL known; response blocked | None recorded | No approved automated access configured | U selected examples only | U | U / disabled | NEEDS_APPROVAL; no approved transport |
| TikTok Commercial Content API | Historical approved-client implementation | None recorded | TikTok client credentials absent | U, prior implementation EU-first | U | U / disabled | BLOCKED |
| Named Apify candidates / LOOOT | Historical documented platform/client paths; current docs blocked | No vendor selected, no dataset license | APIFY_TOKEN/LOOOT_TOKEN absent | U | U; marketplace service availability ≠ data rights | U / disabled | NEEDS_APPROVAL |
| Authorized import | Local code exercised with synthetic fixtures | Attestation required per real dataset | No external credential needed | Supports supplied US records, not retrieval | Depends on dataset permission; operator-declared | No media fetch | Import-ready; no actual real dataset supplied |
| Fixture test | Local synthetic files | Test-only | Not applicable | No real inventory | Synthetic test use | Reserved example URLs only | DEMO only |

U = UNVERIFIED. Open-source MIT licenses concern code reuse, not data collection/storage/redistribution. This phase writes original code and reuses only existing DROPSpy helpers. AdsLibrary's custom license and unlicensed ad-scraper code were not copied.

## Approval evidence required before live

Record approving entity, dated terms/reference/version, approved purpose, countries, corpus and filter/field scope, expiration/revocation conditions, request quotas, retention/deletion (raw and derived), media-display/archive rights and redistribution restrictions. Configure credentials only through secure environment settings. Do not place secrets in JSON manifests, URLs, logs, reports, `.env.example` or chat.

Two controls apply: research Access config must be enabled/APPROVED with a meaningful rights reference; existing database registry must separately be approved, live-enabled, ready and support the query country/filters/corpus. Configuration values record operator decisions; they do not create external permission. Production defaults were not changed.

AUTHORIZED_IMPORT and FIXTURE_TEST use the existing import gate. Synthetic markers are rejected in real mode. Existing provider dataset reads cannot launch actor runs; all paid execution is blocked until a true provider-enforced budget mechanism is reviewed. No budget approval has been received during this task.

## Evidence, retention and URL handling

Research artifacts contain mode, source, corpus, query, timestamps, approval status, scope hash and original row. Structured credential keys/query parameters are redacted on disk. Free text can still contain sensitive content: artifacts are operator-controlled, not published raw by default. Keep only synthetic fixtures and sanitized connection-probe metadata in Git.

Research artifacts are local files, **not covered by the v0.2 database retention worker**. Apply approved deletion periods to pilot output directories; do not treat local output as permanent storage permission. The bridge imports through authorized-file (or demo for fixtures); original collection source remains nested in `_acquisition` raw evidence, while top-level registry source accurately names the file intake. Existing DB raw TTL policy applies after import, with normalized projection retention described in the v0.2 guide. Dataset-specific stricter terms require implementing them before import.

Transport is HTTPS, exact-host, GET-only, no redirects, bounded timeout/bytes/retries. 401/403/challenge is terminal. No CAPTCHA bypass, rotating identities, session hijack or undocumented web endpoint fallback. Returned media/landing URLs are stored as evidence only, never fetched by this harness. Missing source facts remain null; query market is not delivery proof.
