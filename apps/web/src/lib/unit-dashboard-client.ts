/* Client API màn "Dashboard đơn vị" — bức tranh của MỘT phạm vi (toàn Tập đoàn · một khu vực · một
   đơn vị thành viên): thu mua · tiêu thụ · tồn kho · chỉ tiêu năm. Chỉ đọc (GET).
   Kiểu dữ liệu bám đúng hợp đồng plans/260924-dashboard-don-vi/api-contract.md.
   Số `null` = CHƯA CÓ SỐ (không phải 0) — web hiện "—", biểu đồ để trống chứ không vẽ 0. */

import { apiFetch } from "./http";
import type { StockGroupBy, StockSeries } from "./series-client";
import type { StockCoverage } from "./unit-analytics-client";

const BASE = "/api/unit-dashboard";

type Num = number | null;

export type DashScope = "group" | "region" | "unit";

/** Phạm vi đang xem — server trả kèm mọi khối số liệu. `child` = chiều của `breakdown`. */
export type ScopeInfo = {
  scope: DashScope;
  key: string | null;
  label: string;
  child: "region" | "company" | null;
  child_label: string | null;
};

export type ScopeCatalog = {
  /** group: chọn được Tập đoàn/khu vực/đơn vị · unit: tài khoản đơn vị (chỉ đơn vị được gán). */
  mode: "group" | "unit";
  regions: { name: string; units: number }[];
  units: { name: string; region: string | null }[];
  default: { scope: DashScope; key: string | null };
  today: string;
};

/** Gộp theo ngày (`as_of` = YYYY-MM-DD) hay theo tháng (`as_of` = YYYY-MM, kỳ > 62 ngày). */
export type Bucket = "day" | "month";

export type PurchaseBlock = {
  scope: ScopeInfo; date_from: string; date_to: string; bucket: Bucket;
  totals: {
    qty_latex: Num; qty_cup: Num; qty_lace: Num; qty_finished: Num;
    qty_material: Num; qty_total: Num;
    price_latex_avg: Num; price_cup_avg: Num; price_lace_avg: Num; price_finished_avg: Num;
    days: Num; no_purchase_days: Num;
  };
  price_units: { latex: string; cup: string; lace: string; finished: string };
  trend: { as_of: string; qty_latex: Num; qty_cup: Num; qty_lace: Num; qty_finished: Num;
           price_latex_avg: Num }[];
  finished_by_grade: { grade: string; qty: Num; price_avg: Num }[];
  breakdown: { label: string; qty_material: Num; qty_finished: Num; price_latex_avg: Num }[];
  warnings: string[];
};

export type ConsumptionQtys = {
  qty: Num; qty_long_term: Num; qty_spot: Num; qty_unknown_type: Num;
  qty_export: Num; qty_domestic: Num; qty_internal: Num;
};

export type ConsumptionBlock = {
  scope: ScopeInfo; date_from: string; date_to: string; bucket: Bucket;
  totals: ConsumptionQtys & {
    revenue_ty: Num; avg_price_trieu: Num;
    lines: Num; days: Num; missing_fx_lines: number;
  };
  trend: (ConsumptionQtys & { as_of: string; revenue_ty: Num })[];
  by_grade: { grade: string; qty: Num; revenue_ty: Num; avg_price_trieu: Num }[];
  breakdown: { label: string; qty: Num; revenue_ty: Num; avg_price_trieu: Num }[];
  warnings: string[];
};

export type StockBlock = {
  scope: ScopeInfo; as_of: string;
  totals: {
    not_warehoused: Num; warehoused: Num; total: Num; material: Num;
    signed_undelivered: Num;
    tradable: Num;                  // có thể ÂM: đã ký giao nhiều hơn tồn đang có
    age_days: Num; dates: string[];
  };
  by_grade: { grade: string; qty: number }[];
  coverage: StockCoverage | null;
  latest_stock_day: string | null;
  breakdown: { label: string; total: Num; signed_undelivered: Num; tradable: Num;
               material: Num; as_of: string | null }[];
  warnings: string[];
};

export type DashStockView = Exclude<StockGroupBy, "region">;

export type DashStockSeries = StockSeries & { scope: ScopeInfo; date_from: string; date_to: string };

export type TargetKey = "purchase" | "sales_spot" | "revenue";

export type TargetsBlock = {
  scope: ScopeInfo; year: number;
  date_from: string; date_to: string;
  /** % thời gian đã qua của năm tại `date_to` — mốc so tiến độ. */
  time_pct: number;
  items: { key: TargetKey; label: string; unit: string;
           done: Num; plan: Num; pct: Num; note: string }[];
  breakdown: { label: string; purchase_pct: Num; sales_spot_pct: Num; revenue_pct: Num }[];
  warnings: string[];
};

/** Tham số chung của các endpoint số liệu. `asOf` rỗng = server tự lấy min(đến ngày, hôm nay). */
export type DashQuery = {
  scope: DashScope;
  key: string | null;
  from: string;
  to: string;
  asOf: string;
};

export type DashSeriesQuery = DashQuery & { view: DashStockView };

function dashQueryString(q: DashQuery, extra: Record<string, string> = {}): string {
  const p = new URLSearchParams({ scope: q.scope, date_from: q.from, date_to: q.to, ...extra });
  if (q.scope !== "group" && q.key) p.set("key", q.key);
  if (q.asOf) p.set("as_of", q.asOf);
  return p.toString();
}

export const fetchDashScopes = () => apiFetch<ScopeCatalog>(`${BASE}/scopes`);

export const fetchDashPurchase = (q: DashQuery) =>
  apiFetch<PurchaseBlock>(`${BASE}/purchase?${dashQueryString(q)}`);

export const fetchDashConsumption = (q: DashQuery) =>
  apiFetch<ConsumptionBlock>(`${BASE}/consumption?${dashQueryString(q)}`);

export const fetchDashStock = (q: DashQuery) =>
  apiFetch<StockBlock>(`${BASE}/stock?${dashQueryString(q)}`);

export const fetchDashTargets = (q: DashQuery) =>
  apiFetch<TargetsBlock>(`${BASE}/targets?${dashQueryString(q)}`);

export const fetchDashStockSeries = (q: DashSeriesQuery) =>
  apiFetch<DashStockSeries>(`${BASE}/stock-series?${dashQueryString(q, { view: q.view })}`);
