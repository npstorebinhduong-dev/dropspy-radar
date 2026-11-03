# Provider comparison — no live vendor validation

2026-11-03 UTC. All five Apify listing probes below failed at environment proxy CONNECT 403. Provider availability, current schemas, contractual rights and prices have **not** been verified. Actor names are identifiers supplied by the user or historical repo evidence, not capability claims.

| Candidate | Intended evaluation corpus (not verified coverage) | Evidence obtained | US / keyword / advertiser | Creative / landing / pagination | Refresh / stability | Price per 1,000 valid unique records | Rights / retention / redistribution | Outcome |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [locaihost/facebook-ad-library](https://apify.com/locaihost/facebook-ad-library) | Meta paid-ad candidate | Listing request blocked; no current listing body | UNVERIFIED each | UNVERIFIED each | UNVERIFIED each | N/A — no quote/run | UNVERIFIED each | NEEDS_APPROVAL / network BLOCKED |
| [steadyfetch/facebook-ad-library-scraper](https://apify.com/steadyfetch/facebook-ad-library-scraper) | Meta paid-ad candidate | Listing request blocked | UNVERIFIED each | UNVERIFIED each | UNVERIFIED each | N/A | UNVERIFIED each | NEEDS_APPROVAL / network BLOCKED |
| [silentflow/tiktok-creative-ads-scraper](https://apify.com/silentflow/tiktok-creative-ads-scraper) | Possible TikTok selected creative examples; verify actual corpus | Listing request blocked | UNVERIFIED each | UNVERIFIED each | UNVERIFIED each | N/A | UNVERIFIED each | NEEDS_APPROVAL / network BLOCKED |
| [data_xplorer/tiktok-ads-scraper](https://apify.com/data_xplorer/tiktok-ads-scraper) | TikTok ad candidate; library vs curated vs organic unresolved | Listing request blocked | UNVERIFIED each | UNVERIFIED each | UNVERIFIED each | N/A | UNVERIFIED each | NEEDS_APPROVAL / network BLOCKED |
| [curious_coder/facebook-ads-library-scraper](https://apify.com/curious_coder/facebook-ads-library-scraper) | Additional Meta candidate | Phase 2 B1 references invocation; current listing blocked | Historical country input is not current US result evidence | Historical mapper is not verified vendor schema | UNVERIFIED | N/A | UNVERIFIED each; upstream code has no reusable license | NEEDS_APPROVAL / network BLOCKED |
| LOOOT API (`api.looot.ai`) | Additional multi-source orchestration candidate; library and Top Ads separate | Historical MIT client/catalog, Phase 2 L1/L2/L7; no current vendor-doc response in Phase 3A | Historical US Top Ads input only, current discovery U | Historical mapper/run polling only, current fields U | UNVERIFIED | N/A; historical fallback prices not used | UNVERIFIED each | UNVERIFIED / not configured |

These are candidates, not vetted licensed providers. No ranking by output quality or operating cost is supportable yet. No free trial, paid actor, login or provider API was invoked. Error rate and field completeness for all candidates are **N/A**, not 100% error or 0% completeness: documentation network probes are not data runs.

## Vendor evaluation after access

1. Confirm exact actor identity/version and whether it retrieves paid ads, a selected transparency sample, curated ads or organic posts. Inspect input and output schema and methods; reject bypass/unauthorized-session dependencies.
2. Obtain provider terms applicable to acquisition, commercial analysis, display, derived data, storage, retention, deletion and redistribution. Provider service terms and underlying platform permissions are separate. Ask for source provenance; the actor publisher's name is not proof.
3. Verify each of the five US keywords with a ≤50-record cap and serial requests. Record actual input, run ID, timestamp, cap, source-reported totals, truncation and invoice/usage cost. API uptime/history must be evidenced over repeated observations, not inferred from one successful run.
4. Verify advertiser discovery independently from keyword search; preserve Page/business IDs and pagination. Determine whether an advertiser filter narrows a keyword or returns all its ads. The prototype currently uses the intersection; it does not claim all-advertiser inventory.
5. Manually inspect original source URLs from the resulting sample, without bypassing access gates. Record paid evidence, market semantics, creative availability and product destination independently.

`effective_USD_per_1000 = 1000 × actual_total_USD / valid_unique_ads`. Include failed/pending run charges, minimum/platform/compute charges and duplicates in the numerator; exclude duplicate/invalid records from the denominator. If cost or valid unique count is unknown or count is zero, the result is null. Never substitute advertised price for actual spend.

## Adapter delivered

`ProviderDatasetAdapter` implements the standard **existing Apify dataset GET** path with bearer header, offset pagination, configured exact-column mapping and pinned host. It does not invoke any of these actors, implement their unknown schemas, purchase data or provide keyword discovery. A required dataset query manifest prevents presenting an unrelated dataset as a keyword result.

Paid execution is deliberately unavailable: a CLI number alone cannot enforce a vendor bill. `paid=true` is denied even if a local budget flag is supplied. An actor-run adapter requires a reviewed vendor-enforced spend cap, approval, idempotent creation/poll/recovery and cost settlement before implementation. Authorized dataset download also needs confirmed access/egress rights; `paid=false` is appropriate only after verifying that this read has no paid execution/billing effect.
