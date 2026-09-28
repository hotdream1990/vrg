# Hợp đồng API — sản lượng còn phải giao (backlog)

Mọi số là TẤN (gốc quy khô khi có, như cột tiêu thụ). `null` = chưa có số, KHÁC 0.

## 1. Service `app/services/contract_backlog.py`

```python
def backlog_on(as_of: str, companies: list[str] | None = None,
               grades: list[str] | None = None) -> dict[str, dict]:
    """{đơn vị: Backlog} tại ngày as_of (YYYY-MM-DD)."""
```

`Backlog` (một đơn vị):
```jsonc
{
  "spot_undelivered": 123.4,        // HĐ chuyến đã ký chưa giao (không thuộc HĐ mẹ có cam kết)
  "lt_unlinked_undelivered": 50.0,  // HĐ dài hạn KHÔNG thuộc HĐ mẹ có cam kết: đã ký chưa giao
  "unknown_undelivered": 0.0,       // hợp đồng chưa khai loại, không thuộc HĐ mẹ có cam kết
  "master_committed": 1000.0,       // Σ cam kết của HĐ mẹ có SL, hiệu lực chồng lên năm của as_of
  "master_delivered": 400.0,        // Σ đã giao (≤ as_of, lũy kế từ ngày ký) thuộc các HĐ mẹ đó
  "master_remaining": 600.0,        // Σ còn phải giao của HĐ mẹ CÒN hiệu lực tại as_of
  "master_expired_short": 0.0,      // HĐ mẹ hết hạn trước as_of mà chưa giao đủ — KHÔNG vào phải giao
  "masters": 3,                     // số HĐ mẹ có cam kết được tính
  "master_pct": 40.0,               // master_delivered / master_committed * 100; null nếu committed = 0
  "lt_remaining": 650.0,            // = master_remaining + lt_unlinked_undelivered
  "to_deliver": 773.4,              // = spot_undelivered + lt_remaining + unknown_undelivered
  "items": [                        // từng HĐ mẹ có cam kết, xếp remaining giảm dần
    {"id": 1, "code": "…", "master_type": "long_term", "customer_id": 9,
     "sign_date": "2026-01-05", "expiry_date": "2026-12-31",
     "committed": 302.4, "delivered": 120.0, "remaining": 182.4, "pct": 39.7, "expired": false}
  ]
}
```
Hiệu lực trong năm: `sign_date IS NULL OR sign_date <= as_of` VÀ `expiry_date IS NULL OR expiry_date >= <01/01 năm của as_of>`.
Hết hạn: `expiry_date < as_of`.
`grades` → cam kết và đã giao chỉ cộng dòng có chủng loại trong danh sách; khối 3 dùng `undelivered_on(..., grades)`.

## 2. `GET /api/sales-contracts/consumption` — thêm khoá `backlog`

```jsonc
{ "by_company": {…}, "undelivered": {…},   // GIỮ NGUYÊN
  "backlog": { "<đơn vị>": Backlog },        // MỚI — as_of = date_to, gộp đơn vị sáp nhập như `undelivered`
  "backlog_as_of": "2026-09-26" }
```

## 3. Thống kê tiêu thụ — cảnh báo đơn giá sai đơn vị tính

`consumption_report(...)` mỗi dòng/tổng có thêm `bad_price_lines` (int) = số dòng bán có đơn giá quy
đổi > trần `ANOMALY_SALE_PRICE_MAX` (VND: giá; ngoại tệ có tỷ giá: giá × tỷ giá / 1e6). `warnings` thêm
câu nêu số dòng + tên đơn vị. Khối Chỉ tiêu dashboard coi `bad_price_lines > 0` như `no_revenue_lines`
(để trống % doanh thu, `note` nói rõ lý do). Thẻ KPI Doanh thu dashboard đọc `totals.bad_price_lines`.

## 4. `GET /api/unit-dashboard/outlook` — tiến độ bán hàng cả năm (chốt 26/09/2026)

Tham số giống các endpoint dashboard khác (`scope`, `key`, `date_from`, `date_to`). Ngày tính
`as_of = min(date_to, hôm nay)`; năm = năm của `as_of`; lũy kế = 01/01 → as_of.
Chốt nghiệp vụ (chủ dự án 26/09): **KH bán hàng = KH khai thác + KH thu mua** (cột D/E/F biểu Ban
TTKD); **doanh thu dự kiến = doanh thu lũy kế + SL còn phải giao × giá bán BQ lũy kế của CHÍNH đơn vị**.

```jsonc
{
  "scope": {…}, "year": 2026, "as_of": "2026-09-26",
  "lt": {                             // HĐ dài hạn theo HĐ mẹ — CẢ PHẠM VI
    "committed": 165233.0, "delivered": 82501.0, "remaining": 80000.0, "pct": 49.9,
    "masters": 150, "expired_short": 120.0, "unlinked_undelivered": 5000.0 },
  "backlog": {                        // còn phải giao đến cuối năm — CẢ PHẠM VI
    "spot_undelivered": 30000.0, "lt_remaining": 85000.0, "unknown_undelivered": 0.0,
    "to_deliver": 115000.0 },
  "volume": {                         // so KH bán hàng
    "delivered_ytd": 403412.0,        // cả phạm vi
    "projected": 518412.0,            // cả phạm vi = delivered_ytd + backlog.to_deliver
    "plan_exploit": 14743.0, "plan_purchase": 105700.0, "plan_total": 120443.0,  // Σ rổ
    "basket_projected": 20000.0,      // Σ projected của RỔ
    "pct": 16.6,                      // basket_projected / plan_total * 100; null nếu rổ rỗng
    "units_planned": 3,               // rổ = đơn vị ĐÃ NHẬP KH khai thác (kể cả 0) và KH cộng > 0
    "units_missing_exploit": 35,      // đơn vị có KH thu mua mà CHƯA nhập KH khai thác (ngoài rổ)
    "note": "…" },
  "revenue": {
    "done_ytd": 21641.7,              // tỷ đồng, cả phạm vi
    "expected_rest": 6200.0,          // tỷ đồng, cả phạm vi (to_deliver × giá BQ đơn vị)
    "projected": 27841.7,             // cả phạm vi
    "plan": 9817.1, "basket_projected": 10500.0, "pct": 107.0,  // rổ = đơn vị có KH doanh thu
    "units_planned": 27, "note": "…" },   // pct null khi rổ có đơn vị thiếu tỷ giá/đơn giá/đơn giá sai
  "breakdown": [                      // theo chiều con (khu vực · đơn vị), rỗng khi xem 1 đơn vị
    { "label": "Đông Nam Bộ",
      "lt_committed": 0, "lt_delivered": 0, "lt_remaining": 0, "lt_pct": null,
      "spot_undelivered": 0, "to_deliver": 0, "delivered_ytd": 0, "projected": 0,
      "plan_exploit": null, "plan_purchase": null, "plan_total": null, "qty_pct": null,
      "revenue_projected": null, "plan_revenue": null, "revenue_pct": null } ],
  "items": [ /* chỉ khi scope = unit: danh sách HĐ mẹ (BacklogItem) */ ],
  "warnings": []
}
```
Đơn vị còn phải giao mà chưa có giá bán BQ (chưa giao lần nào trong năm) → phần đó CHƯA định giá,
không mượn giá đơn vị khác; `revenue.note` nói rõ số tấn chưa định giá.
