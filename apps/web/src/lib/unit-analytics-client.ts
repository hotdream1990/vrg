/* Client API các màn THỐNG KÊ số liệu đơn vị nhập (thu mua · tiêu thụ · tồn kho · tình trạng nộp).
   Chỉ đọc, chỉ dành cho chuyên viên/admin có quyền `unit_daily` (đơn vị thành viên dùng màn nhập). */

import { authHeaders } from "./auth-token";
import { API, apiFetch } from "./http";

export type Opt = { value: string; label: string };
export type FilterUnit = { name: string; region: string | null; has_factory: boolean };
export type FilterCatalog = {
  units: FilterUnit[]; regions: string[]; grades: string[];
  materials: Opt[]; contracts: Opt[]; channels: Opt[]; sources: Opt[];
};

/** Bộ lọc chung của mọi màn thống kê (mảng rỗng = không lọc). */
export type StatsFilters = {
  from: string; to: string;
  companies: string[]; regions: string[]; grades: string[];
  materials?: string[];      // thu mua: latex | cup | finished
  contract?: string[];       // tiêu thụ: long_term | spot
  channel?: string[];        // tiêu thụ: export | domestic
  groupBy: string;
  /** Chế độ CHI TIẾT (groupBy="none") cắt trang ở server — trang đang xem. */
  page?: number;
};

/** Màn TỒN KHO đi theo trục "ngày chốt" (số thời điểm) chứ không theo khoảng kỳ như các màn khác. */
export type StockFilters = {
  asOf: string;
  /** Số ngày được phép lùi khi đơn vị chưa nhập đúng ngày chốt (0 = chỉ lấy số nhập đúng ngày). */
  maxAgeDays: number;
  companies: string[]; regions: string[]; grades: string[];
  groupBy: string;
};

export type StatsRow = { key: string; label: string; region: string | null; [k: string]: unknown };
export type StatsReport = {
  date_from?: string; date_to?: string; group_by: string; detail?: boolean;
  rows: StatsRow[]; totals: StatsRow; warnings: string[];
  /** Chỉ có ở chế độ chi tiết: tổng số dòng khớp lọc (rows chỉ là trang đang xem). */
  total?: number;
  /** Chỉ có ở màn tồn kho: ngày chốt + độ phủ số liệu. */
  as_of?: string;
  max_age_days?: number;
  coverage?: StockCoverage;
};

/** Độ phủ ảnh chụp tồn kho: bao nhiêu đơn vị có số, đơn vị nào chưa nhập. */
export type StockCoverage = {
  units_expected: number;
  units_counted: number;
  /** Đã nộp nhưng khai "không phát sinh tồn kho" → không có số để cộng (khác với chưa nhập). */
  no_stock: { company: string; as_of: string }[];
  missing: { company: string; has_factory: boolean }[];
};

/** Số dòng mỗi trang ở chế độ chi tiết — khớp mặc định của server. */
export const DETAIL_PAGE_SIZE = 100;

export type StatusCell = "ok" | "no_purchase" | "none";
export type StatusRow = {
  company: string; region: string | null; cells: Record<string, StatusCell>;
  filled: number; no_purchase: number; missing: number; last_day: string | null;
};
export type StatusReport = {
  kind: string; dates: string[]; rows: StatusRow[];
  totals: { expected: number; filled: number; no_purchase: number; missing: number };
};

const BASE = "/api/unit-daily/analytics";

/** Bộ lọc → query string (mảng rỗng bị bỏ qua để URL gọn và server hiểu là "không lọc"). */
export function statsQuery(f: StatsFilters): string {
  const p = new URLSearchParams({ date_from: f.from, date_to: f.to, group_by: f.groupBy });
  const put = (k: string, v?: string[]) => { if (v?.length) p.set(k, v.join(",")); };
  put("companies", f.companies);
  put("regions", f.regions);
  put("grades", f.grades);
  put("materials", f.materials);
  put("contract", f.contract);
  put("channel", f.channel);
  if (f.groupBy === "none") {
    p.set("page", String(f.page ?? 1));
    p.set("page_size", String(DETAIL_PAGE_SIZE));
  }
  return p.toString();
}

export const fetchFilterCatalog = () => apiFetch<FilterCatalog>(`${BASE}/filters`);

export const fetchPurchaseStats = (f: StatsFilters) =>
  apiFetch<StatsReport>(`${BASE}/purchase?${statsQuery(f)}`);

export const fetchConsumptionStats = (f: StatsFilters) =>
  apiFetch<StatsReport>(`${BASE}/consumption?${statsQuery(f)}`);

/** Bộ lọc tồn kho → query string (trục ngày chốt, không có date_from/date_to). */
export function stockQuery(f: StockFilters): string {
  const p = new URLSearchParams({
    as_of: f.asOf, max_age_days: String(f.maxAgeDays), group_by: f.groupBy,
  });
  const put = (k: string, v: string[]) => { if (v.length) p.set(k, v.join(",")); };
  put("companies", f.companies);
  put("regions", f.regions);
  put("grades", f.grades);
  return p.toString();
}

export const fetchStockStats = (f: StockFilters) =>
  apiFetch<StatsReport>(`${BASE}/stock?${stockQuery(f)}`);

export const fetchSubmissionStatus = (kind: string, f: StatsFilters) => {
  const p = new URLSearchParams({ kind, date_from: f.from, date_to: f.to });
  if (f.companies.length) p.set("companies", f.companies.join(","));
  if (f.regions.length) p.set("regions", f.regions.join(","));
  return apiFetch<StatusReport>(`${BASE}/status?${p.toString()}`);
};

/** Tải Excel của bảng đang xem (đúng bộ lọc hiện tại) — fetch kèm token rồi lưu file. */
async function saveXlsx(url: string, filename: string): Promise<void> {
  const res = await fetch(`${API}${BASE}/${url}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Không tải được file Excel.");
  const href = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 60_000);
}

export const downloadStatsXlsx = (kind: "purchase" | "consumption", f: StatsFilters) =>
  saveXlsx(`${kind}.xlsx?${statsQuery(f)}`, `thong-ke-${kind}-${f.from}-den-${f.to}.xlsx`);

export const downloadStockXlsx = (f: StockFilters) =>
  saveXlsx(`stock.xlsx?${stockQuery(f)}`, `thong-ke-ton-kho-ngay-${f.asOf}.xlsx`);
