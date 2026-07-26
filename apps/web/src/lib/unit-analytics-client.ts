/* Client API các màn THỐNG KÊ số liệu đơn vị nhập (thu mua · tiêu thụ · tồn kho · tình trạng nộp).
   Chỉ đọc, chỉ dành cho chuyên viên/admin có quyền `unit_daily` (đơn vị thành viên dùng màn nhập). */

import { authHeaders } from "./auth-token";
import { API, apiFetch } from "./http";

export type Opt = { value: string; label: string };
export type FilterUnit = { name: string; region: string | null; has_purchase_plan: boolean; has_factory: boolean };
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
  source?: string[];         // tiêu thụ: sales (mủ thu mua) | sales_own (mủ khai thác)
  groupBy: string;
};

export type StatsRow = { key: string; label: string; region: string | null; [k: string]: unknown };
export type StatsReport = {
  date_from: string; date_to: string; group_by: string; detail?: boolean;
  rows: StatsRow[]; totals: StatsRow; warnings: string[];
};

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
  put("source", f.source);
  return p.toString();
}

export const fetchFilterCatalog = () => apiFetch<FilterCatalog>(`${BASE}/filters`);

export const fetchPurchaseStats = (f: StatsFilters) =>
  apiFetch<StatsReport>(`${BASE}/purchase?${statsQuery(f)}`);

export const fetchConsumptionStats = (f: StatsFilters) =>
  apiFetch<StatsReport>(`${BASE}/consumption?${statsQuery(f)}`);

export const fetchStockStats = (f: StatsFilters) =>
  apiFetch<StatsReport>(`${BASE}/stock?${statsQuery(f)}`);

export const fetchSubmissionStatus = (kind: string, f: StatsFilters) => {
  const p = new URLSearchParams({ kind, date_from: f.from, date_to: f.to });
  if (f.companies.length) p.set("companies", f.companies.join(","));
  if (f.regions.length) p.set("regions", f.regions.join(","));
  return apiFetch<StatusReport>(`${BASE}/status?${p.toString()}`);
};

/** Tải Excel của bảng đang xem (đúng bộ lọc hiện tại) — fetch kèm token rồi lưu file. */
export async function downloadStatsXlsx(kind: "purchase" | "consumption" | "stock",
                                        f: StatsFilters): Promise<void> {
  const res = await fetch(`${API}${BASE}/${kind}.xlsx?${statsQuery(f)}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Không tải được file Excel.");
  const href = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = href;
  a.download = `thong-ke-${kind}-${f.from}-den-${f.to}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 60_000);
}
