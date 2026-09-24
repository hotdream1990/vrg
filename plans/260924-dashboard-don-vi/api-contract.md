# Hợp đồng API — Dashboard đơn vị

Base: `/api/unit-dashboard` · tất cả là GET · cần đăng nhập (Bearer).

## Tham số chung của các endpoint số liệu
| Tham số | Ý nghĩa |
|---|---|
| `scope` | `group` \| `region` \| `unit` |
| `key` | tên khu vực (scope=region) hoặc tên đơn vị (scope=unit); bỏ trống khi scope=group |
| `date_from`, `date_to` | kỳ xem, `YYYY-MM-DD` |
| `as_of` | ngày chốt tồn kho (tuỳ chọn) — mặc định = min(date_to, hôm nay) |

Tài khoản đơn vị gửi scope/key ngoài phạm vi được gán → **403**. Tên khu vực/đơn vị không tồn tại → **404**.
Số `null` = CHƯA CÓ SỐ (không phải 0) → web hiện "—".

Mọi endpoint số liệu trả kèm:
```ts
type ScopeInfo = {
  scope: "group" | "region" | "unit";
  key: string | null;
  label: string;                         // "Toàn Tập đoàn" | "Khu vực Tây Nguyên" | tên đơn vị
  child: "region" | "company" | null;    // chiều của `breakdown` (group→khu vực, region→đơn vị, unit→không có)
  child_label: string | null;            // "Khu vực" | "Đơn vị"
};
```

## 1. `GET /scopes`
```ts
type ScopeCatalog = {
  mode: "group" | "unit";      // group: chọn được Tập đoàn/khu vực/đơn vị · unit: tài khoản đơn vị
  regions: { name: string; units: number }[];      // [] khi mode=unit
  units: { name: string; region: string | null }[]; // mode=unit: chỉ đơn vị được gán
  default: { scope: "group" | "region" | "unit"; key: string | null };
  today: string;               // YYYY-MM-DD theo giờ VN
};
```

## 2. `GET /purchase`
```ts
type PurchaseBlock = {
  scope: ScopeInfo; date_from: string; date_to: string;
  bucket: "day" | "month";               // kỳ > 62 ngày → gộp theo tháng
  totals: {
    qty_latex: number|null; qty_cup: number|null; qty_lace: number|null; qty_finished: number|null;
    qty_material: number|null;           // nước + chén + dây (tử số % KH)
    qty_total: number|null;              // gồm cả thành phẩm
    price_latex_avg: number|null; price_cup_avg: number|null; price_lace_avg: number|null;
    price_finished_avg: number|null;     // triệu đ/tấn
    days: number|null; no_purchase_days: number|null;
  };
  price_units: { latex: string; cup: string; lace: string; finished: string };
  trend: { as_of: string;                // "YYYY-MM-DD" (bucket=day) hoặc "YYYY-MM" (bucket=month)
           qty_latex: number|null; qty_cup: number|null; qty_lace: number|null;
           qty_finished: number|null; price_latex_avg: number|null }[];
  finished_by_grade: { grade: string; qty: number|null; price_avg: number|null }[]; // giảm dần theo qty
  breakdown: { label: string; qty_material: number|null; qty_finished: number|null;
               price_latex_avg: number|null }[];           // [] khi child=null
  // KHÔNG có % kế hoạch ở đây: % so chỉ tiêu năm chỉ nằm ở /targets (lũy kế từ 01/01), tránh
  // hai con số % khác nghĩa trên cùng một màn.
  warnings: string[];
};
```

## 3. `GET /consumption`
```ts
type ConsumptionBlock = {
  scope: ScopeInfo; date_from: string; date_to: string; bucket: "day" | "month";
  totals: {
    qty: number|null; qty_long_term: number|null; qty_spot: number|null; qty_unknown_type: number|null;
    qty_export: number|null; qty_domestic: number|null; qty_internal: number|null;
    revenue_ty: number|null;             // tỷ đồng
    avg_price_trieu: number|null;        // triệu đ/tấn
    lines: number|null; days: number|null; no_revenue_lines: number;   // lần giao thiếu tỷ giá HOẶC đơn giá
  };
  trend: { as_of: string; qty: number|null; qty_long_term: number|null; qty_spot: number|null;
           qty_unknown_type: number|null; qty_export: number|null; qty_domestic: number|null;
           qty_internal: number|null; revenue_ty: number|null }[];
  by_grade: { grade: string; qty: number|null; revenue_ty: number|null; avg_price_trieu: number|null }[];
  breakdown: { label: string; qty: number|null; revenue_ty: number|null; avg_price_trieu: number|null }[];
  warnings: string[];
};
```

## 4. `GET /stock`
```ts
type StockBlock = {
  scope: ScopeInfo; as_of: string;
  totals: { not_warehoused: number|null; warehoused: number|null; total: number|null;
            material: number|null; signed_undelivered: number|null; tradable: number|null; // có thể ÂM
            age_days: number|null; dates: string[] };
  by_grade: { grade: string; qty: number }[];           // tồn thành phẩm theo chủng loại, giảm dần
  coverage: StockCoverage | null;                       // cùng kiểu `unit-analytics-client.StockCoverage`
  latest_stock_day: string | null;                      // ngày chốt trống → gợi ý ngày gần nhất có số
  breakdown: { label: string; total: number|null; signed_undelivered: number|null;
               tradable: number|null; material: number|null; as_of: string|null }[];
  warnings: string[];
};
```

## 5. `GET /stock-series?view=warehouse|grade|structure|free_grade` (+ tham số chung)
Cùng khuôn `/api/series/stock` (`lib/series-client.ts` → `StockSeries`) + `scope: ScopeInfo`:
`{ date_from, date_to, group_by, start_floor, series:[{key,label}], rows:[{as_of,total,units_counted,values}], pending:[{as_of,units_counted}] }`.
Cửa sổ tối đa 180 ngày, kết thúc ở min(date_to, hôm nay).

## 6. `GET /targets`
```ts
type TargetsBlock = {
  scope: ScopeInfo; year: number;
  date_from: string;            // 01/01 của năm
  date_to: string;              // min(date_to, hôm nay)
  time_pct: number;             // % thời gian đã qua của năm tại date_to (mốc so tiến độ)
  // done/plan/pct tính trên RỔ ĐƠN VỊ ĐƯỢC GIAO chỉ tiêu đó (units_planned); đơn vị chưa được giao
  // mà có số KHÔNG vào tử số — tổng cả phạm vi nói trong `note`. plan null = chưa giao chỉ tiêu.
  items: { key: "purchase" | "sales_spot" | "revenue"; label: string; unit: string;
           done: number|null; plan: number|null; pct: number|null; units_planned: number;
           note: string }[];
  // Tiến độ lũy kế theo chiều con (group→khu vực, region→đơn vị); [] khi scope=unit.
  // Sắp theo thứ tự khu vực/đơn vị như các màn khác; pct null = chưa giao chỉ tiêu hoặc thiếu tỷ giá.
  breakdown: { label: string; purchase_pct: number|null; sales_spot_pct: number|null;
               revenue_pct: number|null }[];
  warnings: string[];
};
```
