# DROPSpy Opportunity Score — research proposal v0.2

**Đây là thiết kế chưa triển khai.** v0.1 giữ nguyên. Score 0–100 là thứ tự ưu tiên nghiên cứu trong dataset có scope, không xác suất thắng, doanh số, ROAS hay lợi nhuận. Không huấn luyện/calibrate bằng business outcomes trong Phase 2.

## Heuristic thực sự có code ở nguồn

| Nguồn | Implementation | Thuật toán quan sát | Có thể học / không mang sang |
| --- | --- | --- | --- |
| B | `WinnerDetector.evaluateWinner` [B4](REPOSITORY_AUDIT.md#b4) | 35% longevity `min(days/30,1)`, 25% scaling score, 15% engagement normalized thresholds, 15% impressions volume, 10% lastSeen recency. Tiers 0.2/0.4/0.6/0.8 | Học component explanation; không copy code (no license), tier labels hoặc “probability/profitable” claims |
| B | `SpendEstimator` [B5](REPOSITORY_AUDIT.md#b5) [B13](REPOSITORY_AUDIT.md#b13) | CPM per niche + assumed daily impression tiers; long-run/engagement/production heuristics choose phase; spend=impressions/1000×CPM×days | Không dùng spend giả định làm observed signal. Longevity bị đếm lại trong scaling; confidence tăng từ duration không là kiểm chứng |
| C | `get_champions` [C10](REPOSITORY_AUDIT.md#c10) | Group variants, active ads, longest span trước; round-robin theo company | Học advertiser-balanced discovery, không coi là product success estimator |
| L | `anglesOf`, `offersOf`, `summarize` [L4](REPOSITORY_AUDIT.md#l4) [L5](REPOSITORY_AUDIT.md#l5) | Substring/regex tags, counts, median/longest duration, CTA/landing tallies | Dễ giải thích, làm baseline rules; không có opportunity score trong nguồn |
| M/F/T/A | Parser/query/filter/diff [M4](REPOSITORY_AUDIT.md#m4) [F5](REPOSITORY_AUDIT.md#f5) [T3](REPOSITORY_AUDIT.md#t3) [A4](REPOSITORY_AUDIT.md#a4) | Không tìm product opportunity ranking hoàn chỉnh trong reviewed paths | Không suy ad parser class “Product” có winning-product algorithm |
| D v0.1 | `score` [D3](REPOSITORY_AUDIT.md#d3) | 40 span / 25 current text variants / 20 same-name advertiser ad count / 15 HTTPS URL | DEMO heuristic hữu ích cho UI; chưa product identity, frequency, saturation, page quality hoặc confidence gating |

B còn cho impression score=0.5 khi thiếu dữ liệu và lastSeen null có thể thành active; organic plays được map impressions [B12](REPOSITORY_AUDIT.md#b12). Vì thế không tái sử dụng trực tiếp scoring assumptions dù implementation tồn tại. Các nhận xét trên là static findings, chưa regression-test source B.

## Đơn vị tính và thời gian

Tính theo **product cluster × thị trường × source cohort × cửa sổ 28 ngày**, không chỉ từng ad. `product_cluster_id` ban đầu là human-reviewed canonical landing/variant grouping; không gộp tất cả sản phẩm trên cùng domain. Chưa match được product → trả ad-level exploratory signals, chưa trả product opportunity rank.

Tách `source_delivery_start/end` với `observed_at`, `first_observed/last_observed`; mỗi metric giữ evidence IDs, source/run/query/version, n records, time window, precision, inferred flag và confidence. Chỉ dùng content loại **paid_ad** được xác nhận cho paid-ad score; organic/top-ads/decorative demo là cohort riêng.

## Công thức đề xuất

Sáu yếu tố cơ hội có trọng số tổng bằng 1; Data Confidence là yếu tố thứ bảy điều chỉnh mức công bố:

| Factor | Weight | Giá trị x trong [0,1] và evidence cần có | Confidence caveat |
| --- | ---: | --- | --- |
| L Advertising Longevity | .22 | `min(log1p(observed_span_days)/log1p(60),1)` trên các ad của product, aggregate median theo advertiser để một brand không chiếm toàn bộ; ít nhất 2 sightings. Source delivery span trình bày riêng | Span không continuous delivery; sparse observation giảm q; một sighting không đủ |
| T Creative Testing Frequency | .18 | `min(new_unique_creative_families_28d / 8,1)` trong stable collection panel, variants/family được dedup content; count và normalized per-observed-week cùng hiển thị | Thiếu baseline hoặc panel thay đổi → unknown; không dùng cards count làm frequency |
| A Advertiser Diversity | .12 | `min(log1p(independent_verified_advertisers)/log1p(6),1)` cho product trong cửa sổ; entity resolution loại duplicate pages cùng brand | Không biết owner độc lập → low confidence, không gộp theo name đơn giản |
| R Landing Conversion Readiness | .18 | Rubric 5 hạng mục bằng nhau: offer/price rõ; product/variant info; CTA/cart có thể quan sát; shipping/returns; contact/privacy/trust disclosures. Mỗi item 0/0.5/1 có URL/snapshot/time | Chỉ audit nội dung được phép; không mua hàng, không đo actual CVR; HTTPS riêng không đủ |
| S Low Observed Saturation | .15 | Stable category/product panel: `1 - clamp((g - .1)/.9,0,1)` với `g=new_independent_advertisers_28d/max(prior_panel_advertisers,1)`; display raw numerator/denominator | Chỉ là supply acceleration trong panel, **không toàn thị trường**; prior cohort=0/thiếu baseline → unknown, không tự max score |
| D Product Differentiation | .15 | Human rubric 3 nhóm (feature/use-case distinction, offer/bundle distinction, messaging distinction), mỗi nhóm 0/0.5/1 với so sánh cohort cụ thể; mean | Khác creative không chắc khác product; unknown nếu chưa review comparables. Embedding similarity chỉ P2 hỗ trợ reviewer |

Các divisor 60/8/6 và ngưỡng .1/.9 là **tham số thiết kế**, không số liệu tìm được trên thị trường. Version hóa và hiệu chỉnh qua validation; chưa khẳng định optimal. A đo bằng chứng nhiều advertiser độc lập còn S đo tăng cạnh tranh của panel qua thời gian; theo dõi correlation/double-counting, không dùng cùng một count làm cả hai.

Gọi `available_i` ∈ {0,1}; unknown không phải x=0. `q_i` ∈ [0,1] là evidence-quality rubric: provenance verified, freshness, observation coverage và entity-match review; thành phần thiếu bằng chứng nhận 0. q là mức đánh giá evidence, **không posterior probability**.

```text
W = sum(w_i * available_i)
if W == 0: score = null, status = insufficient_data
Q = sum(w_i * available_i * x_i) / W
C = sum(w_i * available_i * q_i)       # [0,1], includes missing-weight penalty
opportunity_score = round(100 * Q * C, 1)
```

**Publish/rank gate**: chỉ công bố score xếp hạng khi C≥.60, product match reviewed, L và T có baseline hợp lệ, ≥2 observations cách nhau ≥7 ngày và market/source cohort tương thích. Nếu không: `score=null`, `status=insufficient_data` và chỉ trả components/coverage. Có thể hiển thị provisional diagnostic nội bộ có nhãn, không dùng để sort “winning products”. Full DEMO được gắn `is_demo` và chỉ xếp trong DEMO; không lọt vào real leaderboard.

Không impute một “neutral” điểm cho missing metric. Không tăng confidence chỉ vì longevity. Confidence rubric khởi đầu: fresh ≤7d=1, 8–28d=.5, >28d=0; provenance unsupported=0; temporal completeness dùng số completed expected runs/thực expected runs với outage riêng; product/entity confidence do reviewer. Giá trị q cuối là min của các rubric liên quan để một điểm yếu không bị bù bằng field khác. Không tự tạo sample coverage khi source không cung cấp denominator; q temporal coverage không thay corpus coverage.

## Ví dụ số học tổng hợp, không phải số liệu quảng cáo

Với **synthetic** x=(.8,.6,.5,.7,.4,.5), all available và q=1, Q=.605, C=1 → **60.5/100**. Đây chỉ chứng minh công thức, không kết quả smoke/live. Thiếu R/D thì W=.67; công thức có missing penalty và vẫn phải qua gate; không đơn giản chia lại trọng số rồi tuyên bố tự tin tương đương full evidence. Nếu L/T baseline không có, public score=null dù còn nhiều fields khác.

## Explanation contract đề xuất

```json
{
  "version": "opportunity-0.2-proposed",
  "entity_type": "product_cluster",
  "product_cluster_id": "human-reviewed-id",
  "market": "US",
  "source_cohort": "authorized-dataset-id",
  "window_days": 28,
  "score": null,
  "status": "insufficient_data",
  "is_demo": false,
  "components": [
    {
      "metric": "creative_testing_frequency",
      "value": null,
      "weight": 0.18,
      "confidence": 0,
      "source_ids": [],
      "observation_ids": [],
      "reason": "No comparable completed baseline runs",
      "inferred": true
    }
  ]
}
```

Example contract không tuyên bố có dataset real trong môi trường. Mỗi component cần raw numerator/denominator, normalized value, q, contribution, evidence timestamp, transformation version và missing_reason. `source_quality` không được chọn chỉ vì repo nhiều stars.

## Validation trước khi bật score

1. Pure unit tests: bounds/weights, null path, no-demodata-mixing, reproducibility, duplicate invariance, missing/rounding/UTC cases; unknown không tăng confidence, adding duplicate ad không tăng T/A.
2. Fixture histories: repeated creatives/CDN URL expiry, partial scans, same-brand multi-page, product variants, discontinued offers, false missing, panel drift. Mỗi change có expected component explanation.
3. Human review tối thiểu 30 product clusters đa category/market trong authorized sample (mục tiêu thiết kế, chưa chạy): reviewers độc lập, ghi inter-rater agreement/false merge và reasons. Không coi sample này representative US market.
4. So sánh ranking với baseline longevity-only; đo usefulness của shortlist qua reviewer labels và rank stability. Không dùng metric này xác nhận sales/profit. Nếu không có labels đáng tin, giữ “exploratory” và gate chặt.
5. Version parameters/data/feature snapshot, backfill không sửa evidence cũ; định kỳ kiểm selection bias, missingness và ranking correlation. Spend/ROAS/revenue inference ngoài scope, không xuất hiện trong công thức.
