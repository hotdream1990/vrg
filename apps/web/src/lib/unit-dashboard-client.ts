/* Client API màn "Dashboard đơn vị" — bức tranh của MỘT phạm vi (toàn Tập đoàn · một khu vực · một
   đơn vị thành viên): thu mua · tiêu thụ · tồn kho · chỉ tiêu năm. Chỉ đọc (GET).
   Kiểu dữ liệu bám đúng hợp đồng plans/260924-dashboard-don-vi/api-contract.md.
   Số `null` = CHƯA CÓ SỐ (không phải 0) — web hiện "—", biểu đồ để trống chứ không vẽ 0. */

import { apiFetch } from "./http";
import type { BacklogItem } from "./sales-contract-client";
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
  qty: Num; qty_long_term: Num; qty_spot: Num; qty_principle: Num; qty_unknown_type: Num;
  qty_export: Num; qty_domestic: Num; qty_internal: Num;
};

export type ConsumptionBlock = {
  scope: ScopeInfo; date_from: string; date_to: string; bucket: Bucket;
  totals: ConsumptionQtys & {
    revenue_ty: Num; avg_price_trieu: Num;
    lines: Num; days: Num;
    /** Lần giao chưa tính được doanh thu (thiếu tỷ giá hoặc đơn giá) — doanh thu đang thiếu phần đó. */
    no_revenue_lines: number;
    /** Dòng bán có đơn giá quy đổi vượt trần = nghi nhập sai đơn vị tính → doanh thu bị ĐỘI lên.
     *  Vắng = API cũ. */
    bad_price_lines?: number;
  };
  trend: (ConsumptionQtys & { as_of: string; revenue_ty: Num })[];
  by_grade: { grade: string; qty: Num; revenue_ty: Num; avg_price_trieu: Num }[];
  breakdown: { label: string; qty: Num; revenue_ty: Num; avg_price_trieu: Num;
               bad_price_lines?: number }[];
  warnings: string[];
};

/** Độ phủ + đơn vị đang dùng số CŨ (tick "không phát sinh tồn kho" → giữ lần khai gần nhất,
 *  `as_of` = ngày khai thật). `stale` vắng = API cũ. */
export type DashStockCoverage = StockCoverage & {
  stale?: { company: string; as_of: string; age_days: number }[];
};

export type StockBlock = {
  /** `as_of` = ngày chốt · `auto_as_of` = server tự lấy (ngày cuối của biểu đồ diễn biến, đã đủ
   *  đơn vị khai) vì người dùng để "Tự động". */
  scope: ScopeInfo; as_of: string; auto_as_of?: boolean;
  totals: {
    not_warehoused: Num; warehoused: Num; total: Num; material: Num;
    signed_undelivered: Num;
    tradable: Num;                  // có thể ÂM: đã ký giao nhiều hơn tồn đang có
    /** `dates` = NGÀY KHAI thật của các số đang cộng · `age_days` = số cũ nhất (ngày). */
    age_days: Num; dates: string[];
  };
  by_grade: { grade: string; qty: number }[];
  coverage: DashStockCoverage | null;
  latest_stock_day: string | null;
  /** `as_of` = ngày khai (null khi nhóm gồm nhiều ngày) · `age_days` = số cũ nhất trong nhóm. */
  breakdown: { label: string; total: Num; signed_undelivered: Num; tradable: Num;
               material: Num; as_of: string | null; age_days?: Num }[];
  warnings: string[];
};

export type DashStockView = Exclude<StockGroupBy, "region">;

/** `start_floor` = null khi xem MỘT đơn vị (không kẹp mốc đủ độ phủ của Tập đoàn/khu vực). */
export type DashStockSeries = Omit<StockSeries, "start_floor"> & {
  scope: ScopeInfo; date_from: string; date_to: string; start_floor: string | null;
};

export type TargetKey = "purchase" | "goods" | "sales_spot" | "revenue";

export type TargetsBlock = {
  scope: ScopeInfo; year: number;
  date_from: string; date_to: string;
  /** % thời gian đã qua của năm tại `date_to` — mốc so tiến độ. */
  time_pct: number;
  /** done/plan/pct tính trên rổ `units_planned` đơn vị ĐƯỢC GIAO chỉ tiêu đó. `scope_done` = số
   *  thực hiện của CẢ phạm vi (gồm đơn vị chưa giao KH) — cùng gốc với thẻ KPI; vắng = API cũ. */
  items: { key: TargetKey; label: string; unit: string;
           done: Num; plan: Num; pct: Num; units_planned: number; note: string;
           scope_done?: Num }[];
  breakdown: { label: string; purchase_pct: Num; goods_pct: Num; sales_spot_pct: Num; revenue_pct: Num }[];
  warnings: string[];
};

/* ── Tiến độ bán hàng cả năm (plans/260926-hd-dai-han-phai-giao/api-contract.md mục 4) ──────────
   Sản lượng: TẤN (gốc quy khô như tiêu thụ) · doanh thu: TỶ ĐỒNG. Số "cả phạm vi" và số của RỔ (đơn
   vị có KH) là hai gốc khác nhau. Khoá con để Partial: API viết song song, thiếu khoá thì hiện "—". */

/** HĐ dài hạn theo HĐ mẹ có cam kết — cả phạm vi. `expired_short`: cam kết CHƯA KÝ phụ lục của HĐ mẹ
 *  đã hết hạn (KHÔNG vào phải giao) · `unlinked_undelivered`: phụ lục dài hạn ngoài HĐDH có cam kết, đã ký
 *  chưa giao · `missing_master_undelivered`: HĐ dài hạn chưa gán HĐ mẹ (lỗi dữ liệu) ·
 *  `remaining_after_year`: phần còn lại thuộc HĐ mẹ còn hiệu lực sau 31/12 / không thời hạn. */
export type OutlookLt = { committed: Num; delivered: Num; remaining: Num; pct: Num; masters: Num;
                          expired_short: Num; unlinked_undelivered: Num; missing_master_undelivered: Num;
                          remaining_after_year: Num };

/** Còn phải giao đến cuối năm — cả phạm vi.
 *  to_deliver = spot_undelivered + principle_undelivered + lt_remaining + unknown_undelivered. */
export type OutlookBacklog = { spot_undelivered: Num; principle_undelivered: Num; lt_remaining: Num;
                               unknown_undelivered: Num; to_deliver: Num };

/** KH bán hàng = KH khai thác + KH thu mua + KH hàng hóa. delivered_ytd/projected: cả phạm vi; plan_* ·
 *  basket_projected · pct: rổ `units_planned` đơn vị đã nhập KH khai thác. */
export type OutlookVolume = {
  delivered_ytd: Num; projected: Num; plan_exploit: Num; plan_purchase: Num; plan_goods: Num;
  plan_total: Num; basket_projected: Num; pct: Num; units_planned: Num; units_missing_exploit: Num; note: string;
};

/** DT dự kiến = đã thực hiện + SL còn phải giao × giá bán BQ lũy kế của chính đơn vị.
 *  done_ytd/expected_rest/projected: cả phạm vi; plan · basket_projected · pct: rổ có KH DT. */
export type OutlookRevenue = {
  done_ytd: Num; expected_rest: Num; projected: Num;
  plan: Num; basket_projected: Num; pct: Num; units_planned: Num; note: string;
};

export type OutlookBreakdownRow = {
  label: string;
  lt_committed: Num; lt_delivered: Num; lt_remaining: Num; lt_pct: Num;
  spot_undelivered: Num; principle_undelivered: Num;
  /** Ô dài hạn của "còn phải giao" — `lt_remaining` ở trên chỉ là cam kết HĐDH còn lại. */
  backlog_lt_remaining: Num; unknown_undelivered: Num;
  to_deliver: Num; delivered_ytd: Num; projected: Num;
  plan_exploit: Num; plan_purchase: Num; plan_goods: Num; plan_total: Num; qty_basket_projected?: Num;
  qty_pct: Num;
  revenue_projected: Num; plan_revenue: Num; revenue_basket_projected?: Num; revenue_pct: Num;
};

/** `as_of` = min(đến ngày, hôm nay), lũy kế từ 01/01 · `breakdown` rỗng khi xem 1 đơn vị ·
 *  `items` (từng HĐ mẹ) chỉ khi xem 1 đơn vị. */
export type OutlookBlock = {
  scope: ScopeInfo; year: number; as_of: string;
  lt?: Partial<OutlookLt>; backlog?: Partial<OutlookBacklog>;
  volume?: Partial<OutlookVolume>; revenue?: Partial<OutlookRevenue>;
  breakdown?: OutlookBreakdownRow[]; items?: BacklogItem[]; warnings?: string[]; critical_errors?: string[];
};

/** Tham số chung của các endpoint số liệu. `asOf` rỗng = server tự lấy ngày gần nhất đã đủ đơn vị
 *  khai tồn kho (ngày cuối của biểu đồ diễn biến tồn kho). */
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

// `signal`: huỷ lượt gọi cũ khi đổi bộ lọc — mỗi khối là vài báo cáo nặng, bấm kỳ liên tục mà không
// huỷ thì server vẫn tính hết các lượt đã bị bỏ.
export const fetchDashPurchase = (q: DashQuery, signal?: AbortSignal) =>
  apiFetch<PurchaseBlock>(`${BASE}/purchase?${dashQueryString(q)}`, { signal });

export const fetchDashConsumption = (q: DashQuery, signal?: AbortSignal) =>
  apiFetch<ConsumptionBlock>(`${BASE}/consumption?${dashQueryString(q)}`, { signal });

export const fetchDashStock = (q: DashQuery, signal?: AbortSignal) =>
  apiFetch<StockBlock>(`${BASE}/stock?${dashQueryString(q)}`, { signal });

export const fetchDashTargets = (q: DashQuery, signal?: AbortSignal) =>
  apiFetch<TargetsBlock>(`${BASE}/targets?${dashQueryString(q)}`, { signal });

export const fetchDashOutlook = (q: DashQuery, signal?: AbortSignal) =>
  apiFetch<OutlookBlock>(`${BASE}/outlook?${dashQueryString(q)}`, { signal });

export const fetchDashStockSeries = (q: DashSeriesQuery, signal?: AbortSignal) =>
  apiFetch<DashStockSeries>(`${BASE}/stock-series?${dashQueryString(q, { view: q.view })}`, { signal });
