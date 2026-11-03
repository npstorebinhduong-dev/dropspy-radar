# US ads pilot results — blocked live, fixture verified

Run date: 2026-11-03 UTC. **No live acquisition pilot ran successfully. No actual US ad inventory was obtained.** Technical acceptance is partial: adapters/harness/fixture intake are delivered; live evidence and manual source validation remain blocked.

## Actual external observations

[public-probes.json](evidence/public-probes.json): 11 bounded public website/document requests, all failed at the environment proxy with CONNECT 403. These are connection probes, not ad search results. They do not measure vendor data error rate or establish any current platform policy.

[credential-readiness.json](evidence/credential-readiness.json): presence-only checks show no Meta, TikTok, Apify or LOOOT credentials. No login, token extraction, actor execution, paid request or alternate transport was used. No actual permitted real file was supplied.

## Five-keyword plan and actual status

[disabled-preflights.json](evidence/disabled-preflights.json) records 35 local approval checks: seven source/actor candidates × five keywords. All terminate as `needs_approval` before a data request. This is reproducible gate evidence, **not 35 live pilot runs**. TikTok official API additionally remains unapproved with US scope unverified; no transport was implemented without current documentation/permission.

| Keyword | Target | Live ad requests | Returned / unique ads | Coverage / duplicate rate | Source total / data latency / actual billed cost | Manual original-ad review |
| --- | --- | --- | --- | --- | --- | --- |
| solar garden lights | US | UNRUN | N/A | N/A | N/A | UNRUN |
| pet grooming | US | UNRUN | N/A | N/A | N/A | UNRUN |
| portable blender | US | UNRUN | N/A | N/A | N/A | UNRUN |
| posture corrector | US | UNRUN | N/A | N/A | N/A | UNRUN |
| car accessories | US | UNRUN | N/A | N/A | N/A | UNRUN |

No paid API invocation occurred. No invoice/charge was measured; actual live pilot cost is **N/A**, not an inferred zero-dollar provider trial. Local compute cost is not metered here. Connection duration fields belong solely to the failed probes, not acquisition latency.

## Measured synthetic benchmark (FIXTURE_TEST only)

Artifacts: [benchmark](evidence/fixture-benchmark.json), [import file](evidence/fixture-import.json), [isolated import proof](evidence/fixture-import-proof.json). Run with `python scripts/run_acquisition_fixture.py` using the repository venv.

| Metric | Synthetic result |
| --- | ---: |
| Returned rows | 3 |
| Unique source ad IDs + platform | 2 |
| Valid nonempty source-ID rate | 100% |
| Advertiser ID coverage | 66.67% |
| Copy coverage | 100% |
| Media URL coverage | 33.33% |
| Landing URL coverage | 100% |
| Source start-date coverage | 33.33% |
| Duplicate rate among rows with IDs | 33.33% |
| Imported DEMO ads / raw evidence rows | 2 / 2 |
| REAL rows | 0 |
| Re-upload | Same import job |
| Distinct exact product URL groups | 2; same domain, different variant query |
| Provider-reported USD cost | null / unknown |

Duration is measured and recorded in the artifact for this fixture run only; it is not source throughput or a live performance estimate. Fixture completeness remains partial, despite exhausting a local file, because file exhaustion does not establish full source inventory. The IDs, advertisers, media and landing URLs are explicitly synthetic reserved-example data; their real existence was not checked or claimed.

## Provenance and current dashboard

The test suite verifies fixture adapter → benchmark → explicit file export → existing v0.2 preview/batch import → Meta/US/keyword search → evidence detail, with fixture markers and `_acquisition` metadata preserved. REAL lookup of these ads is rejected. Existing seven-view browser regression also remains in the validation plan; results are recorded in the run guide after execution.

The file bridge's registry source is `demo` or `authorized-file`; original collection source/corpus/query/rights/scope/raw row remain in `_acquisition`. It is not misrepresented as a directly approved production collector. Export skips records lacking required source ad ID, placement/aggregate platform, advertiser name or declared country; query intent never supplies those missing facts.

## Advertiser expansion and enrichment

Bounded one-hop keyword → advertiser-ID → advertiser+keyword queries are implemented and fixture-tested. The synthetic overlap case adds one unique ad; no live uplift, incremental cost or coverage ratio is established. IDs are deduplicated; the original per-keyword record cap is shared by the expansion. The current official prototype intersects advertiser and keyword; querying all advertiser ads needs verified source semantics before a separate capability is added.

Exact landing URLs retain product/variant parameters and are grouped separately from domain. This is URL grouping, not verified product identity. No remote landing/media fetch, ranking interpretation, scheduled monitor or stopped-ad inference was added. Partial/capped/missing scans cannot mark ads inactive.

## Blockers and next bounded run

1. Apply/review network draft for exact documentation/source hosts; recheck enforced runtime policy.
2. Verify current US corpus/filters and terms, commercial analysis/display rights, retention and approval. Obtain source credentials where required through secure settings.
3. For a provider, obtain a licensed dataset/sample first or a reviewed vendor-enforced budget before implementing paid execution. No budget approval was supplied in this task.
4. Replace disabled config with reviewed source/corpus/market/fields and registry approval. Fixture tests do not authorize that change.
5. Run five keywords serially, cap ≤50 records each initially (hard maximum 100), preserve raw/checkpoint/observed facts, and review a small actual sample using [manual review template](manual-review.example.csv).
6. Import only records with adequate provenance into the existing dashboard. Report actual counts, null rates, elapsed data-request time and actual source-reported/invoiced charges. Repeat under the same scope to assess stability; no false stopped status on missing rows.
