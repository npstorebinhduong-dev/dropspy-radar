# Phase 3B — First real source: blocked at environment proxy

Observed 2026-11-03T16:50:28.671255+00:00–2026-11-03T16:50:28.780602+00:00 (UTC). Base `929a280`; branch `research/phase3b-network-first-real-proof`.

## Decision

**Network recovery is not demonstrated. All eleven repeated URLs still fail at HTTPS CONNECT with proxy status 403. No destination HTTP response was received. No real ad was retrieved or imported.** Per the requested Task 1 stop condition, Meta/provider data acquisition and the REAL pipeline were not attempted beyond these public connectivity probes. No bypass, paid actor, purchase, token use or fixture relabeling occurred.

## Applied policy versus saved configuration

- Runtime status is current (`observations_current=true`), `restricted/enforced`, desired and observed spec revision `1`, custom `allowed_hosts=[]`. The complete effective list excludes the target Meta/Apify/TikTok research hosts.
- The selected executor policy file independently excludes those target hosts. HTTP_PROXY/HTTPS_PROXY and lowercase equivalents point to `http://proxy:8080`; no proxy credentials are printed. Target Meta/Apify hosts are not exempted by NO_PROXY. CA-related settings are present; TLS verification was left enabled.
- Saved draft revision `8` includes Meta, TikTok and Apify hosts. Its base version matches the runtime's current configuration version. This proves a desired/applied discrepancy, **not the user's publish history**. The current instance has not been observed enforcing that allowlist. Possible wrong environment/version binding or publication/application failure cannot be distinguished with the available evidence.
- No source secrets or outbound identities are configured in the observed runtime. That is a later access prerequisite, not the cause established for these CONNECT failures.
- Available tools expose status/diagnostics and draft saving; no runtime apply/restart/publish operation is available here. No further draft edit was made: the required hosts are already present in the saved draft.

Evidence: [runtime versus draft](evidence/phase3b/runtime-vs-draft.json), [executor/proxy snapshot](evidence/phase3b/executor-network.json). Snapshots omit credential values.

## Repeated experiment

Ran the original `scripts/probe_acquisition_sources.py` once unchanged: 11/11 CONNECT403. Then added separate output selection and failure-layer attribution and repeated the same eleven URLs for the detailed evidence below. Preserved Phase 3A evidence unchanged. Each request is serial and bounded to 15 seconds / approximately 1 MiB; no authenticated or paid API is called.

| Probe | Destination HTTP status | Proxy CONNECT status | Response source | Elapsed ms |
| --- | --- | --- | --- | ---: |
| meta_public | N/A | 403 | environment proxy | 37 |
| meta_official | N/A | 403 | environment proxy | 14 |
| meta_terms | N/A | 403 | environment proxy | 8 |
| tiktok_top | N/A | 403 | environment proxy | 9 |
| tiktok_official | N/A | 403 | environment proxy | 12 |
| locaihost | N/A | 403 | environment proxy | 10 |
| steadyfetch | N/A | 403 | environment proxy | 6 |
| silentflow | N/A | 403 | environment proxy | 5 |
| data_xplorer | N/A | 403 | environment proxy | 4 |
| curious_coder | N/A | 403 | environment proxy | 6 |
| apify_dataset_docs | N/A | 403 | environment proxy | 6 |

Observation window and individual timestamps/URLs: [Phase 3B probes](evidence/phase3b/public-probes.json). Latency range **4–37 ms** measures immediate proxy rejection, not source response or acquisition latency.

**Comparison:** Phase 3A 11/11 CONNECT403 → Phase 3B 11/11 CONNECT403, identical URLs; destination HTTP responses remain 0. [Machine-readable comparison](evidence/phase3b/comparison.json), [frozen Phase 3A baseline](evidence/phase3b/phase3a-baseline.json).

Failure classification: **proxy denial verified**; destination DNS/TLS, authentication and source restrictions **not evaluated**, because CONNECT was rejected first. Proxy 403 must not be reported as Facebook/Apify HTTP403. A successful future HTTPS response would still not independently prove origin, search results or permission.

## Meta US and provider outcome

| Required question | Actual finding |
| --- | --- |
| Has networking recovered? | No for the requested research destinations; enforced custom allowlist is empty and all probes are denied. This does not imply all Internet/package access fails. |
| Which Meta US source is reachable? | None demonstrated. The public URL already includes `solar garden lights`, US and active ads; it was not reached. Official docs and automated collection terms were also blocked. |
| Does search return results? | UNVERIFIED; no page/body/result inspected. |
| Permitted automated collection and commercial research use? | UNVERIFIED. No current terms or approval could be checked; website visibility would not resolve these questions. |
| Real ads retrieved? | None acquired; search returned/unique counts are N/A, not a successful zero-match result. |
| Which fields actually exist? | N/A: no real source rows, creative, landing URL, advertiser or dates were observed. |
| Imported / duplicate-tested REAL ads? | No. REAL pipeline and real-record duplicate test UNRUN; no actual permitted sample was available. Existing fixture regressions are separate. |
| Cost? | No paid actor/run/purchase; no measured acquisition invoice or live cost. |

Provider review is limited to three Meta candidates: `locaihost/facebook-ad-library`, `steadyfetch/facebook-ad-library-scraper`, and `curious_coder/facebook-ads-library-scraper`. All three listing probes fail before reaching Apify. Current US coverage, keyword/advertiser discovery, schema fields, origin/distribution rights, storage/analysis/display rights, retention and USD/1,000 unique ads are **UNVERIFIED** for each. No sample dataset was discovered or downloaded. The mandatory eleven-URL rerun includes other Phase 3A URLs solely for connectivity comparison; they were not additional provider evaluations.

## Concrete next blocker

Ensure the **environment bound to this running task** is using the intended published configuration/version. Its enforced effective allowlist must include at least `www.facebook.com`, `developers.facebook.com`, `apify.com` and `docs.apify.com` (the saved full probe set also includes `ads.tiktok.com` and `developers.tiktok.com`). If those settings were already published, reconcile/restart the task instance on that version through the supported environment workflow or environment support; do not simply assume another draft save applies it.

Recheck `environment_status`: current/enforced policy and effective target-host membership must change before rerunning these probes. Apply publication/restart through supported controls, never by editing the local policy file or changing proxies/routes. Network permission does not grant data rights; after connectivity, separately verify Meta automation/commercial-use permission or a provider sample license before enabling any collector or REAL import.

## Regression validation

- Full backend: **69 passed, 4 skipped** in 7.53s; one upstream Starlette/AnyIO deprecation warning. Eleven new offline diagnostic tests cover proxy CONNECT403/407, DNS, TLS, timeout, HTTP401/403/429/500, successful shell attribution and credential-safe error persistence. Existing acquisition/import/search/API tests pass.
- The four PostgreSQL-specific tests were skipped because no dedicated TEST_DATABASE_URL was configured for this run; migration/concurrency checks are not claimed as rerun.
- Ruff and Git whitespace checks pass. No UI, Data Core, schema, live adapter activation or AI changes. Frontend build/browser tests were not rerun for this Python diagnostics-only change.

Repeat detailed probes without overwriting Phase 3A:

```sh
.venv/bin/python scripts/probe_acquisition_sources.py --output docs/acquisition/evidence/phase3b/public-probes.json
```
