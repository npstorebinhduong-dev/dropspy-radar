# Data Source & Acquisition Analysis

Ngày audit: 2026-11-03. **Static code review; không có live collection.** Các host/endpoint dưới đây là danh tính interface quan sát trong code, không phải hướng dẫn vượt access control. File/hàm/commit cho mỗi evidence ID nằm ở [audit register](REPOSITORY_AUDIT.md#evidence-register).

## Phân loại nguồn và luồng xử lý

| Repo/path | Nhóm nguồn | Luồng thực sự trong code | Token / quyền | US / EU evidence & caveat |
| --- | --- | --- | --- | --- |
| M | Internal web API, không official Graph | `MetaAdsCollector.search` → `MetaAdsClient.search_ads` → `facebook.com/api/graphql/` → `Ad.from_graphql_response` → filters/dedup/export; cursor/search state và async có code [M1](REPOSITORY_AUDIT.md#m1) [M2](REPOSITORY_AUDIT.md#m2) [M3](REPOSITORY_AUDIT.md#m3) [M4](REPOSITORY_AUDIT.md#m4) | SDK không đòi official app token, có session/fingerprint/challenge plumbing; **không suy ra authorization** | country US/EU params có code; live availability/completeness/permission U |
| F | Public web UI + browser automation + internal payloads | keyword/Page URL → browser/page_flow → embedded JSON + pagination responses → `ad_row` → atomic JSON/CSV + sidecar/diff [F1](REPOSITORY_AUDIT.md#f1) [F2](REPOSITORY_AUDIT.md#f2) [F3](REPOSITORY_AUDIT.md#f3) [F4](REPOSITORY_AUDIT.md#f4) [F5](REPOSITORY_AUDIT.md#f5) | Logged-out path; solver/CDP/paid API options tồn tại, loại khỏi DROPSpy | Meta country params có code; commercial US scope do UI/provider quyết định, không official API guarantee |
| T | EU transparency website + internal API/browser | browser → internal `library.tiktok.com/api/v1/search` → cursor → `parse_search` → region:ad_id rows → coverage metadata/diff [T2](REPOSITORY_AUDIT.md#t2) [T3](REPOSITORY_AUDIT.md#t3) [T4](REPOSITORY_AUDIT.md#t4) [T5](REPOSITORY_AUDIT.md#t5) [T8](REPOSITORY_AUDIT.md#t8) | Browser-minted access header; không coi là API grant; không tái tạo acquisition | 33 supported regions trong code; `US` bị reject [T1](REPOSITORY_AUDIT.md#t1). EU sample không là US inventory |
| C self-host | Wrapper M dependency | configured pages/country → async collector ACTIVE → normalize → PG appearances/creatives → media/S3 → landing links/snapshots [C1](REPOSITORY_AUDIT.md#c1) [C3](REPOSITORY_AUDIT.md#c3) [C8](REPOSITORY_AUDIT.md#c8) | Có source access constraints của dependency; dependency pinned 1.6.0 [C15](REPOSITORY_AUDIT.md#c15) | Country theo page config; active watchlist subset, không global keyword completeness |
| C optional paid | Third-party Apify | recorded actor run → poll/dataset/resume → same normalization/storage [C12](REPOSITORY_AUDIT.md#c12) [C13](REPOSITORY_AUDIT.md#c13) | APIFY token + billing + permitted provider/data contract | Target country không chứng minh toàn thị trường hay quyền media; nhà cung cấp là phụ thuộc riêng |
| A Meta Graph | **Official Meta API client implementation** | `graph.facebook.com/{version}/ads_archive`, access token, serialized params, pagination/retry → MetaGraphSource [A2](REPOSITORY_AUDIT.md#a2) [A5](REPOSITORY_AUDIT.md#a5) | Approved app/user/token/entitlement phải kiểm theo official docs hiện hành | Code/comments nói broad commercial EU-delivered, political ngoài EU; **không xác minh current policy**. Không hứa US commercial discovery |
| A TikTok | **Official TikTok Commercial Content API client implementation** | `open.tiktokapis.com/v2/oauth/token/`, `/v2/research/adlib/ad/query/`, advertiser query; OAuth cache/search_id iterator → normalized media/reach/date [A3](REPOSITORY_AUDIT.md#a3) [A4](REPOSITORY_AUDIT.md#a4) | Approved client và scope; repo không cấp token hoặc quyền research/commercial use | Adapter notes EU-first; quyền/US fields/retention phải xác nhận hiện hành trước pilot |
| A Meta scraper | Public page/internal web payload | keyword/Page → server HTML/Relay first results → contact/creative normalization [A6](REPOSITORY_AUDIT.md#a6) [A7](REPOSITORY_AUDIT.md#a7) | No official token nhưng vẫn cần permitted access | Low-level `country=ALL`; common query không tự đảm bảo country/date/status được áp dụng |
| L | Third-party API orchestration | `/v1/runs?wait=30` + run status → pinned provider catalog → alias normalizer → latest report + budget ledger [L1](REPOSITORY_AUDIT.md#l1) [L2](REPOSITORY_AUDIT.md#l2) [L3](REPOSITORY_AUDIT.md#l3) [L7](REPOSITORY_AUDIT.md#l7) | LOOOT token, credits, vendor/data terms; code MIT không cấp data license | Library vs Creative Center Top Ads là hai corpus; Top Ads input US nhưng selected ads, không census. Không verify provider coverage |
| B Meta | Third-party Apify actor | `curious_coder/facebook-ads-library-scraper` → dataset → NewAd normalization [B1](REPOSITORY_AUDIT.md#b1) | APIFY token, charges, actor/data rights | US default param; actual source results U |
| B TikTok/Instagram | Third-party **organic content** scrapers | Clockworks TikTok video / Instagram posts actor → caption/engagement/media → ads table [B2](REPOSITORY_AUDIT.md#b2) [B3](REPOSITORY_AUDIT.md#b3) [B12](REPOSITORY_AUDIT.md#b12) | APIFY + actor rights, không có chứng cứ paid delivery cho mọi record | Post origin/creator country không ad reached-country; video age không ad longevity |

Publicly visible không có nghĩa tự động được phép mọi cách thu thập/lưu/phân phối. Official endpoint tồn tại trong code không đồng nghĩa người dùng này đã có access hoặc đủ quyền thương mại. Trước live pilot, lưu phiên bản provider terms, approval scope, permitted purposes, geography, retention/deletion và media rights. Không fallback từ API denial sang internal scraping, CAPTCHA solving hay proxy rotation.

## Data contract: trường có code, không bảo đảm có giá trị

Ký hiệu: **mapped** = parser có mapping; **sparse** = có thể thiếu; **derived** = suy từ dữ liệu khác; **absent** = không thấy trong đường đi được xem. Đây là coverage source-code, **không phải tỷ lệ đầy đủ thực đo**.

| Nhóm trường | M/F Meta | T TikTok EU web | A official clients | C tracker / L board / B app | Quy tắc DROPSpy |
| --- | --- | --- | --- | --- | --- |
| Ad/source ID & source URL | mapped; ID/collation fields [M3](REPOSITORY_AUDIT.md#m3) [F2](REPOSITORY_AUDIT.md#f2) | mapped ID + region permalink [T3](REPOSITORY_AUDIT.md#t3) | Meta ID/snapshot; TikTok ID, normalized URL có thể thiếu [A4](REPOSITORY_AUDIT.md#a4) [A5](REPOSITORY_AUDIT.md#a5) | C IDs; L provider ID hoặc content hash fallback; B external ID [C3](REPOSITORY_AUDIT.md#c3) [L3](REPOSITORY_AUDIT.md#l3) [B11](REPOSITORY_AUDIT.md#b11) | Preserve source namespace, ID quality, source URL, query/run provenance |
| Advertiser ID/name | mapped, page info sparse | advertiser **name** mapped; business ID không hiện trong row mapper [T3](REPOSITORY_AUDIT.md#t3) | Meta page ID; TikTok business ID/name mapped [A4](REPOSITORY_AUDIT.md#a4) | C normalized page/company; L name aliases; B creator ≠ advertiser | Name không entity ID; null thay vì invented stable brand |
| Copy/headline/CTA | mapped/sparse; body/card overlays [M3](REPOSITORY_AUDIT.md#m3) [F2](REPOSITORY_AUDIT.md#f2) | title fallback advertiser name; không bằng full ad copy | Meta arrays mapped first creative; TikTok mapper media-only [A4](REPOSITORY_AUDIT.md#a4) [A5](REPOSITORY_AUDIT.md#a5) | L aliases; B AI/organic caption riêng provenance | Giữ original text vs extracted vs model-generated distinct |
| Media | images/videos/cards/URLs mapped | video/image/cover URLs + counts | Meta Graph core creative text không tự trả downloadable file; TikTok media URLs | C mirror+compress; L links-only; B remote actor URLs | Media rights, expiry, SHA-256, fetched_at; URLs không nội dung archive |
| Landing URL/domain | M/F mapped sparse | không thấy landing destination trong parse_search | Meta caption/link-text không mặc định landing destination; TikTok absent in mapper | C canonical landing links; L separates library URL; B organic post URL in landing field | Source URL/post URL ≠ commerce landing. No arbitrary URL fetch from browser |
| Delivery dates | mapped source start/end; F inclusive Pacific-date semantics | first/last shown mapped; derived span | source dates mapped | C source dates + separately first_seen; L aliases collapse source/seen; B uses post created date | Separate delivery_start/end, observed_at, first_observed/last_observed; precision + timezone |
| Active status | mapped when source supplies | hardcoded requested ad_status; audit/rejection code preserved | Meta infers from stop missing, TikTok exact active string | C absent-on-complete inference; L old lastSeen→inactive; B recency heuristic | Tri-state unknown, source_status vs inferred_status, evidence timestamp |
| Country/language/platform | M/F query region vs publisher/languages distinct | query region present | API country/language scope source-specific | B locationCreated/locationName không targeting | Separate query_country, reached_country, advertiser_country, content_origin, placement |
| Spend/impressions/reach | sparse ranges/transparency only; not all US commercial ads | estimated_audience bucket; **không spend/impressions** [T3](REPOSITORY_AUDIT.md#t3) | Meta field groups conditional; TikTok reach compact/range handling [A2](REPOSITORY_AUDIT.md#a2) [A10](REPOSITORY_AUDIT.md#a10) | B organic plays mapped impressions, spend estimates from constants [B12](REPOSITORY_AUDIT.md#b12) [B13](REPOSITORY_AUDIT.md#b13) | Metric name/unit/bounds/reported vs estimated; no recasting reach, plays or audience as impressions |
| Product/price/category | no verified product entity; F price/brand=None [F8](REPOSITORY_AUDIT.md#f8) | class Advertisement not product detector [T11](REPOSITORY_AUDIT.md#t11) | absent product model | C landing catalog proxy; B niche inference; L no product score | Product identity/classification human/derived provenance; never infer orders from ad |
| Sales/revenue/ROAS/profit | **not observed by this audit** | not supplied in reviewed mapping | not part of reviewed query fields | B “winner/profitable” labels don't create ground truth | Do not invent, estimate or display as measured outcomes |

### Empty, estimated và unknown

- Không đổi missing thành 0; 0 là quan sát số 0 với nguồn cụ thể. Unknown filter phải có policy explicit, khác default include-unknown của M [M4](REPOSITORY_AUDIT.md#m4).
- Compact audience/reach strings giữ raw string, numeric interval/rounding nếu có; không coi `11K` là exact 11000 [A10](REPOSITORY_AUDIT.md#a10).
- Collation count là provider grouping; khác số unique visual creatives, khác new variants/week. Source `end_date` hoặc local `last_seen` không chứng minh delivery liên tục.
- Provider API có thể trả empty vì no match, blocked, parse error, quota hoặc partial. Persist `outcome` riêng; `success, 0 ads` không thay mọi loại lỗi [T9](REPOSITORY_AUDIT.md#t9).
- `complete` chỉ nghĩa hoàn thành query/cursor trong giới hạn được nhận; capped/ranked source chưa exhaustiveness. Không gán disappeared/stopped từ top-N hoặc failed scan [F5](REPOSITORY_AUDIT.md#f5) [T5](REPOSITORY_AUDIT.md#t5) [C4](REPOSITORY_AUDIT.md#c4).

## US-first feasibility

**Không repo nào trong 7 repo tự chứng minh đường lấy toàn bộ US commercial Meta + TikTok, không trả phí, được phép và bền vững.** M/F internal/website access rộng hơn về params nhưng permission/uptime U. T rõ ràng không US. A official path phù hợp hướng tuân thủ, nhưng approval/region/purpose gates có thật và chưa xác minh cho user. L có US Top Ads source input qua provider, chỉ selected corpus. B TikTok/IG organic là loại nội dung khác.

Quyết định: US MVP dùng dataset được cấp quyền/import trước; có thể thêm provider US sau contract test, không ép EU data thành US. EU official adapter là track riêng sau xác nhận access. Trường `market_scope` bắt buộc và UI luôn hiển thị corpus, không chỉ cờ quốc gia.

Các tài liệu official cần xác minh trước implementation: [Meta ads_archive](https://developers.facebook.com/docs/graph-api/reference/ads_archive/), [TikTok Commercial Content API](https://developers.tiktok.com/doc/commercial-content-api-getting-started). Đây là references do source clients dẫn; **chưa đọc/xác nhận current docs trực tiếp trong audit này**. Không lấy thủ tục onboarding/token hay thời gian approval trong upstream README làm hướng dẫn hiện hành.

## Smoke-test decision và kết quả thật

Runtime environment metadata không có secret/outbound identity cho nguồn. Presence-only check cho `META_ACCESS_TOKEN`, `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `APIFY_TOKEN`, `LOOOT_TOKEN`, `GEMINI_API_KEY`: **absent**. Không đọc giá trị, không yêu cầu gửi secret chat. Vì chưa có approved source/credential/permission, không chạy collector hay gọi platform endpoints. Không cài upstream dependency; không phát sinh paid call.

| Keyword | Thị trường dự định | Trạng thái | Ads thu được | Field completeness | Latency | Error / reason |
| --- | --- | --- | --- | --- | --- | --- |
| solar garden lights | US, EU pilot riêng | UNRUN | N/A | N/A | N/A | Chưa có authorized source và approval/credentials |
| pet grooming | US, EU pilot riêng | UNRUN | N/A | N/A | N/A | Cùng prerequisite; không gọi nguồn |
| portable blender | US, EU pilot riêng | UNRUN | N/A | N/A | N/A | Cùng prerequisite; không gọi nguồn |

N/A không phải 0 quảng cáo, 0ms hay source error. Đây không phải kết quả test thất bại: test chưa được chạy. Historical fixture counts/upstream README live claims không được dùng thay số liệu đo.

## Pilot nhỏ sau khi được cấp quyền (đề xuất, chưa thực hiện)

1. Operator xác nhận approved source/purpose/market và allowed fields; secret vào secure environment settings. Với source bị denial, dừng, không chuyển transport để né.
2. Isolated container **network disabled mặc định**, non-root, read-only filesystem/source checkout, no Docker socket/host secrets; chỉ bật đúng official/provider hosts theo approval cho live phase. Chỉ inject source credential đó. Không chạy `pip install .`/npm lifecycle upstream trên môi trường chính.
3. Trước live, kiểm pure parser/mapper bằng fixture hợp lệ trong sandbox; timeout/resource cap, checksum response, không eval payload. Approval/licensing chưa đủ thì viết adapter mới từ official contract.
4. Mỗi keyword: một page/request, cap ≤10 records nếu API hỗ trợ, concurrency=1; theo quota/Retry-After. Đo wall time và source HTTP/error, raw count, unique count, null tỷ lệ từng field, query scope, truncation/completeness, actual cost nếu có. Không retry 401/403/CAPTCHA.
5. Redact tokens và personal data trong logs/artifacts; giữ source response chỉ theo retention. Báo rõ sample bias, ngày query, data-as-of. Kết quả chỉ được nâng trạng thái sau chạy thật.
