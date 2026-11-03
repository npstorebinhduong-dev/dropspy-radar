# Phase 3A — Source discovery

Assessment: 2026-11-03 UTC. Baseline `7b76fa9` (v0.2), work branch `research/phase3a-ads-acquisition`. Existing dashboard/API/schema remain unchanged. Six Phase 2 documents and implemented registry/import/ingest paths were inspected. No upstream code was copied or executed.

## Evidence and access conditions

[Eleven public probes](evidence/public-probes.json) cover Meta Library, its automated collection terms and official API documentation, TikTok Creative Center and official documentation, all four requested provider pages, one additional provider and Apify dataset documentation. **Every probe failed at proxy CONNECT 403 before contacting the destination.** No response body, ad record, current price, service uptime or current terms were obtained. This is an environment access blocker; it does not prove that any platform allows or prohibits a particular use.

Runtime reports restricted/enforced networking, no custom allowed hosts, no source credentials or outbound identities. A draft allowlist was saved for documentation hosts; saving does not apply it. Review/save/publish is required in Environment Settings. No attempt was made to bypass the proxy, use an external relay, solve challenges or invoke private web endpoints.

Previous exact-commit static findings remain in [Phase 2 audit](../research/REPOSITORY_AUDIT.md); they are historical source-code evidence, not current live verification. MetaAdsCollector's internal GraphQL transport is not adopted. TikTok organic scrapers are excluded.

## Meta US paid advertisements (P0)

| Requirement | Evidence / prototype | Current live conclusion |
| --- | --- | --- |
| Active keyword + US | Existing public URL parameters; new authorized public first-page adapter | BLOCKED by environment and permission gate; no returned ads |
| Advertiser / Page ID search | Audited SDKs implement it; official prototype supports search_page_ids only when capability-approved | UNVERIFIED live; public prototype rejects advertiser queries |
| Facebook / Instagram / Reels placement | Source publisher fields mapped; multiple/absent placements stay `meta` | Filter semantics/current coverage UNVERIFIED; no assumption Reels is a separately filterable API placement |
| Ad ID, Page ID/name, copy, CTA | Nullable typed mapping from supported embedded/official fields, fixture-tested | Field completeness N/A without live records |
| Image/video, landing URL | Public snapshot URLs mapped where supplied; no media download or landing fetch | Official core response does not establish direct media/commerce links; missing stays null |
| Start date | Source delivery datetime/epoch kept separate from retrieval observation | Live source semantics UNVERIFIED |
| Pagination | Official prototype uses opaque `after` on pinned Graph host, never follows credential-bearing next URL | Current API version/entitlement not verified; public reader explicitly first-page partial |
| Access permission | Separate local config + database registry + current rights review | No approved source. Public visibility alone does not resolve automated collection/commercial reuse rights |

Official endpoint existence does not establish US commercial corpus access. Phase 2 code suggested EU commercial/political differences; current official scope could not be checked. Do not use this report to claim US official API availability or absence.

## TikTok Creative Center US examples (P0)

The requested public page was probed with `region=US`; it was not reached. Keyword, industry, objective, country filters, 7/30/180-day windows, advertiser/brand, landing URL, video and ranking fields are all **UNVERIFIED for this session**. No website UI inspection or sample validation was possible. These requirements must be checked individually after access becomes available; names of UI options are not an API contract.

Always label this corpus `curated_top_ad` (UI/report label CURATED_TOP_ADS). Top Ads is a selected examples corpus, not ALL_PAID_ADS. Organic posts are separate and excluded. The prototype has an explicit `needs_approved_creative_center_transport` outcome; approval alone cannot turn a stub into a collector. An approved provider export can later use the file/dataset path with the same corpus.

## Official APIs and additional candidates

- Meta official prototype is GET-only, requires an operator-verified API version and token, and remains disabled by default. API/purpose/country/field rights must be confirmed before invocation.
- TikTok Commercial Content API: prior audited approved-client implementation is EU-first; current US commercial scope, commercial use and eligibility remain unverified. No TikTok official transport was invented.
- Named Apify actors and additional candidates are compared in [PROVIDER_COMPARISON.md](PROVIDER_COMPARISON.md). A marketplace listing is not a data license.

## Implemented research path

`Access + Query → local/registry gate → adapter page → bounded benchmark/checkpoint → explicit export → existing v0.2 preview/import → current search/detail/evidence`.

Modes OFFICIAL_API / LICENSED_PROVIDER / AUTHORIZED_PUBLIC_SOURCE / AUTHORIZED_IMPORT / FIXTURE_TEST remain distinct in every artifact. Unknown source facts remain null. `target_country` is query intent; an absent record country is not auto-filled from it. Public first-page rows therefore may not qualify for import until a permitted export supplies required market/identity fields. This intentionally surfaces a contract gap instead of fabricating geography.

No production source is selected or enabled. Technical fixtures and acquisition prototypes are delivered; live acceptance remains blocked. See [pilot results](US_ADS_PILOT_RESULTS.md), [rights](DATA_ACCESS_AND_RIGHTS.md), [operating decision](PRODUCTION_SOURCE_RECOMMENDATION.md) and [run guide](README.md).
