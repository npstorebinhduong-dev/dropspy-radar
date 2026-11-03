# Implementation Roadmap — review before coding

Ngày: 2026-11-03. **Phase 2 deliverable chỉ là tài liệu.** v0.1 source/runtime behavior giữ nguyên tại baseline 8330fac. Đề xuất dưới đây cần được duyệt trước coding tiếp theo; không có bước tự động copy hàng loạt repo.

## 10 ưu tiên nên thực hiện

Thứ tự vừa theo dependency vừa theo giá trị cho research workflow. Effort là ước lượng engineer-days, không bao gồm external approval/credentials/legal review; chưa là lịch cam kết.

| # | Priority | Feature / phạm vi | Có gì hiện nay / evidence | Acceptance cụ thể | Effort ước lượng |
| ---: | --- | --- | --- | --- | --- |
| 1 | P0 | Source registry + rights/capabilities/market gate | Minimal interface D; A concept [D6](REPOSITORY_AUDIT.md#d6) [A1](REPOSITORY_AUDIT.md#a1) | Unsupported query denied rõ; US/EU/corpus riêng; live off khi chưa approval | 2–3d |
| 2 | P0 | Provenance và unknown semantics | D observations sparse [D2](REPOSITORY_AUDIT.md#d2) [D4](REPOSITORY_AUDIT.md#d4) | Source/run/evidence IDs cho mỗi imported field/metric; null khác 0; demo isolation | 2–3d |
| 3 | P0 | Authorized JSON/CSV import adapter | Existing demo fixture path; export patterns M/F [M8](REPOSITORY_AUDIT.md#m8) [F6](REPOSITORY_AUDIT.md#f6) | Ingest 3 fixture histories có quyền, validation preview, size caps, no URL fetch | 2–3d |
| 4 | P0 | Alembic + concurrent-safe upsert | D create_all/serial ingest; C appearances [D2](REPOSITORY_AUDIT.md#d2) [C3](REPOSITORY_AUDIT.md#c3) | Migration upgrade/rollback plan, replay và concurrent duplicates không tăng counts | 2–3d |
| 5 | P0 | Search/saved UX theo provenance | Existing Next/FastAPI [D1](REPOSITORY_AUDIT.md#d1) [D5](REPOSITORY_AUDIT.md#d5) | Giữ 7 views; filter scope/date semantics/unknown policy; stable pagination/save tests | 1–2d |
| 6 | P0 | Complete-run comparison & change history | F diff/C complete scan [F5](REPOSITORY_AUDIT.md#f5) [C4](REPOSITORY_AUDIT.md#c4) | Partial/capped/window-exit không stopped; new/changed/source-stopped có evidence | 2–3d |
| 7 | P1 | Creative identity và permitted archive | D text fingerprints; M media; C card keys [D2](REPOSITORY_AUDIT.md#d2) [M6](REPOSITORY_AUDIT.md#m6) [C11](REPOSITORY_AUDIT.md#c11) | Exact hash stable qua CDN URL đổi; rights allowed trước download; media optional | 3–5d |
| 8 | P1 | Landing → reviewed product grouping | C URL canonicalizer [C5](REPOSITORY_AUDIT.md#c5) | Raw+canonical URLs, retain product/variant params, review false merge; no domain-wide collapse | 3–5d |
| 9 | P1 | Opportunity Score v0.2 + explanation | D heuristic/B caution [D3](REPOSITORY_AUDIT.md#d3) [B4](REPOSITORY_AUDIT.md#b4) | Null gate, component evidence/version, demo/real separation, synthetic arithmetic tests | 3–5d |
| 10 | P1 | Watchlists/manual jobs → scheduler | C lock/recovery patterns [C2](REPOSITORY_AUDIT.md#c2) [C12](REPOSITORY_AUDIT.md#c12) | Same-source comparable runs, bounded retries, terminal denied, restart-safe checkpoint | 3–5d |

P0 không yêu cầu paid provider hoặc AI. Bước #3 có thể hoàn thiện với user-owned/authorized dataset; nếu chưa có dataset real, dùng synthetic contract fixtures và gọi rõ “import-ready”, không nói live research-ready. #10 chạy được với fixture/import jobs trước; remote collection vẫn gated.

## Milestones và đường nhanh nhất

### M0 — Phê duyệt thiết kế, không viết ứng dụng trong Phase 2

- Review [audit/license](REPOSITORY_AUDIT.md), [feature matrix](FEATURE_MATRIX.md), [data sources](DATA_SOURCE_ANALYSIS.md), [score](WINNING_PRODUCT_ALGORITHM.md), [architecture](ARCHITECTURE_BLUEPRINT.md).
- Chốt source quyền sử dụng cho US-first và phạm vi sản phẩm. Giữ A/B ở reference-only. Có thể phát triển import pipeline độc lập khi provider chưa được chọn; không chờ secrets cho phần này.
- Current issues triage/official docs/US source terms còn UNVERIFIED, ghi owner và bằng chứng cần bổ sung; không coi đó là kết quả audit đã hoàn tất live.

### M1 — Import-first research MVP (P0, khoảng 2–3 tuần một kỹ sư)

Làm #1–#6 theo thứ tự, chia PR nhỏ: contract/schema → import/upsert → API/filter/provenance → deltas. Ước lượng tổng là design planning, có thể thay đổi sau migration/data review. Source-owned dataset gate tách khỏi software readiness.

Exit criteria:

- Demo hiện có vẫn chạy; lint/typecheck/tests/build/smoke qua khi code thay đổi.
- Có authorized import path cùng schema với demo; no-demo mixing, no external collector activation.
- 3 synthetic history fixtures: complete scan với new/changed; partial scan; capped/sliding selection. No false stopped, stable replay, null/unknown đúng.
- Search/saved/history qua browser/API/PG; source/corpus/time/coverage nhìn rõ. Tài liệu runbook giữ nguyên local-only safety boundary.
- Nếu chỉ synthetic dataset, gọi DEMO/import-ready. Có real imported data không đồng nghĩa có live discovery.

### M2 — Product signals (P1, khoảng 2–3 tuần tiếp theo)

Làm #7–#10, deterministic rules và human review trước AI. Archive opt-in sau media rights. Score chỉ published khi data-confidence/product-match/baseline gate đạt; labels “exploratory opportunity”, không “proven winner”.

Exit criteria: reviewer-confirmed product clusters, duplicate-invariant T/A, preserved variant params, capped/failed source effects shown, restart-safe jobs, explanation reproducible theo feature snapshot. Nghiên cứu chất lượng với 30 reviewed product clusters là **validation target**, chưa có kết quả.

### M3 — Live source pilot (song song tìm access, chỉ code/call sau gate)

- Xác minh current Meta/TikTok official docs và scope với approved app/client; viết adapter mới theo documented API contract. A chứa API shape nhưng license hold không được giải quyết bằng copy đổi tên [A2](REPOSITORY_AUDIT.md#a2) [A3](REPOSITORY_AUDIT.md#a3) [A8](REPOSITORY_AUDIT.md#a8) [A9](REPOSITORY_AUDIT.md#a9).
- US: nếu official scope không bao phủ intended commercial ads, dùng **authorized import** hoặc licensed provider có hợp đồng rõ; không thay bằng internal endpoint hoặc EU corpus. Licensed vendor là optional dependency cho US live, phải thể hiện cost/coverage/retention.
- Pilot 3 keywords theo [test plan](DATA_SOURCE_ANALYSIS.md#pilot-nhỏ-sau-khi-được-cấp-quyền-đề-xuất-chưa-thực-hiện), one-page caps, concurrency=1, isolation, exact outcomes/latency/null counts/actual cost. Nguồn bị từ chối → dừng. Không chạy unknown upstream source trên app host.
- Sau có bằng chứng live mới chọn production quotas, interval, source SLA/cost estimate. Access approval có thể không được cấp; import-first vẫn là usable workflow.

### M4 — P2 sau khi có dữ liệu và nhãn đánh giá

Perceptual creative similarity, product/brand clustering, SSRF-safe landing readiness snapshots, transcript/OCR/AI annotations, saturation cohort analytics, scalable storage/query. Không thêm LLM/vector DB trước khi có use case/labels/cost. Xem matrix về complexity và limitations.

## Reuse shortlist và ràng buộc

| Module/pattern | Nguồn | License | Quyết định tiếp theo |
| --- | --- | --- | --- |
| Pure payload normalization, range handling, filters, exports | M [M3](REPOSITORY_AUDIT.md#m3) [M4](REPOSITORY_AUDIT.md#m4) [M8](REPOSITORY_AUDIT.md#m8) | MIT | Candidate, port selectively with notice; change missing-data semantics deliberately + fixture tests |
| Complete/scope/checksum-aware diff, atomic writer/CSV escaping | F [F5](REPOSITORY_AUDIT.md#f5) [F6](REPOSITORY_AUDIT.md#f6) | MIT | Candidate; adapt dataset/run schema, preserve incomplete/capped distinction |
| Region validation, row key/diff/coverage semantics | T [T1](REPOSITORY_AUDIT.md#t1) [T5](REPOSITORY_AUDIT.md#t5) [T6](REPOSITORY_AUDIT.md#t6) [T7](REPOSITORY_AUDIT.md#t7) | MIT | Candidate pure helpers; no browser/header/challenge code; US remains unsupported |
| Landing canonicalization, appearances, worker lease/recovery, media storage patterns | C [C3](REPOSITORY_AUDIT.md#c3) [C5](REPOSITORY_AUDIT.md#c5) [C8](REPOSITORY_AUDIT.md#c8) [C12](REPOSITORY_AUDIT.md#c12) | MIT | Candidate; audit tracking-param false merge and SSRF/retention; PG queue design riêng |
| Angle/offer rules, idempotency, cost budget | L [L4](REPOSITORY_AUDIT.md#l4) [L6](REPOSITORY_AUDIT.md#l6) [L7](REPOSITORY_AUDIT.md#l7) [L8](REPOSITORY_AUDIT.md#l8) | MIT | Candidate; avoid vendor coupling, replace disk ledger for multi-worker |
| Official API clients/capability layer | A [A1](REPOSITORY_AUDIT.md#a1) [A2](REPOSITORY_AUDIT.md#a2) [A3](REPOSITORY_AUDIT.md#a3) | Custom/ambiguous for commercial reuse | Reference-only until written permission/license clarification; implement own contract from current official docs |
| Intelligence/scoring/Apify/Gemini modules | B [B1](REPOSITORY_AUDIT.md#b1) [B4](REPOSITORY_AUDIT.md#b4) [B6](REPOSITORY_AUDIT.md#b6) | No license found | Do not copy. Independently implement needed features; reject fabricated spend and paid/organic conflation |

Trước **mỗi** code reuse: pin exact SHA/module; inspect module headers + dependency/asset license; retain required copyright/notice; document modifications/attribution in third-party notices; scan for network side effects, credential logging, eval/install scripts; sandbox tests with fixtures; confirm platform/data/media permissions independently. MIT code permission không giải quyết vendor service terms. Phase 2 chưa copy nên chưa thêm third-party code notices vào application.

## Những gì phải tự xây

- Permission/capability registry và source-independent contract gắn market/corpus/completeness.
- Canonical product/advertiser identities; explicit observed vs inferred vs generated facts; versioned provenance per metric.
- Correct concurrent ingestion/queries on current PostgreSQL/FastAPI, migrations, jobs/checkpoints và confidence gating.
- Product scoring/calibration/rubrics, landing readiness, saturation panel; không lấy winner/spend assumptions của B.
- Authentication/multi-user authorization nếu mở deployment; source-level budgets và actual-cost monitoring nếu chọn paid API.

## Rủi ro, dependency và cách xử lý

| Risk | Dấu hiệu / evidence | Hành động |
| --- | --- | --- |
| US commercial inventory không có source được phép | T rejects US; A scope/approval not confirmed [T1](REPOSITORY_AUDIT.md#t1) [A2](REPOSITORY_AUDIT.md#a2) [A3](REPOSITORY_AUDIT.md#a3) | Keep import-first; provider review external gate, no bypass |
| Internal source drift/block | M/F/T browser/internal endpoints [M2](REPOSITORY_AUDIT.md#m2) [F4](REPOSITORY_AUDIT.md#f4) [T8](REPOSITORY_AUDIT.md#t8) | Do not adopt as default; authorized adapter contract tests/terminal denial |
| License scope không rõ | A custom conflict; B absent | No copying; seek clarification separately or independent implementation |
| Sparse/capped observations tạo false inactive | F guards; C inferred end [F5](REPOSITORY_AUDIT.md#f5) [C16](REPOSITORY_AUDIT.md#c16) | Store completeness/cohort and “not observed” state |
| Organic mislabeled paid / fabricated performance | B2/B12/B13 | Separate corpus + metric definitions; no sales claims |
| False creative/product merges | C URL/card keys; L hash fallback [C11](REPOSITORY_AUDIT.md#c11) [L3](REPOSITORY_AUDIT.md#l3) | SHA/content provenance + review, retain identity-changing params |
| Budget runaway / duplicate paid calls | L reservation model [L7](REPOSITORY_AUDIT.md#l7) | Explicit cap + quote + transactional idempotency, pending not failed |
| Credential leakage / unsafe remote content | B logging [B10](REPOSITORY_AUDIT.md#b10); landing URLs external | Redaction, isolated workers, SSRF guards, rights-aware retention |

## Review packet và trạng thái thực hiện

- Đã tạo đúng 6 tài liệu Phase 2; không sửa application, lockfiles, dependency declarations hoặc v0.1 behavior.
- Các source/feature conclusions có exact-commit file/symbol evidence. Issues listing/status còn UNVERIFIED do GitHub dynamic shell/API Forbidden; không báo “no issues”. Official scope docs chưa verified hiện hành.
- Không chạy upstream tests/build/collector; không có live counts/latency/sales metrics. 3-keyword pilot chưa chạy vì chưa có source approval/credentials.
- Chỉ chạy kiểm tra tài liệu (links/anchors/evidence paths/whitespace, docs-only diff). Smoke app v0.1 đã chạy lại và PASS: Next page, proxy, PostgreSQL filtering, saved-ad roundtrip, observations, score, TikTok và advertiser summary. Không rebuild app vì không đổi code.
- Commit trên nhánh `docs/phase2-source-intelligence-audit`. PR nên **stack lên `feat/dropspy-radar-mvp`** khi v0.1 chưa merge main, để diff chỉ gồm tài liệu; nếu base đã merge thì retarget main sau kiểm tra. Không merge/publish/deploy trong Phase 2.
