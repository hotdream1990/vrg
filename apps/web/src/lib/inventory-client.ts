/* Client API Tồn kho Tập đoàn (fact_inventory) — đọc chuỗi tuần + nhập/sửa/xoá. */

import { apiFetch } from "./http";

export type InventoryWeek = {
  as_of: string;
  ton_kho: number | null;
  ton_kho_hd: number | null;
  note: string | null;
  source: string;
};

const req = <T>(path: string, init?: RequestInit): Promise<T> =>
  apiFetch<T>(path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });

export const fetchInventory = () => req<InventoryWeek[]>(`/api/inventory`);

export const upsertInventory = (w: {
  as_of: string; ton_kho: number | null; ton_kho_hd: number | null; note?: string | null;
}) => req<InventoryWeek>(`/api/inventory`, { method: "POST", body: JSON.stringify(w) });

export const deleteInventory = (as_of: string) =>
  req<{ deleted: string }>(`/api/inventory/${as_of}`, { method: "DELETE" });

/* ── Chuỗi tồn kho THEO NGÀY (cộng từ biểu Tồn kho của đơn vị thành viên) ─── */

export type StockGroupBy = "structure" | "grade" | "region";

export type StockSeriesRow = {
  as_of: string;
  total: number | null;                 // tồn kho (tấn) của các đơn vị có số trong ngày
  units_counted: number;
  units_expected: number;
  values: Record<string, number>;       // theo khoá của `series`
};

export type StockSeries = {
  date_from: string;
  date_to: string;
  group_by: StockGroupBy;
  start_floor: string;                  // ngày đầu tiên đơn vị nhập đủ để cộng thành số Tập đoàn
  max_age_days: number;                 // số ngày được phép lấy lại bản ghi cũ của một đơn vị
  series: { key: string; label: string }[];
  rows: StockSeriesRow[];               // ngày TĂNG dần
};

export const fetchStockSeries = (groupBy: StockGroupBy, dateFrom?: string, dateTo?: string) => {
  const p = new URLSearchParams({ group_by: groupBy });
  if (dateFrom) p.set("date_from", dateFrom);
  if (dateTo) p.set("date_to", dateTo);
  return req<StockSeries>(`/api/inventory/series?${p}`);
};

/* ── Tự tính tồn kho từ số liệu đơn vị thành viên ─────────────────────────── */

export type InventoryAutoConfig = {
  enabled: boolean;
  weekday_label: string;
  max_age_days: number;
  recompute_weeks: number;
  last_anchor: string;
};

export type InventoryAutoPreview = {
  as_of: string;
  ton_kho: number | null;
  ton_kho_hd: number | null;
  units_counted: number;
  units_expected: number;
  missing: string[];
  no_stock: string[];
  note: string;
};

export type InventoryRecompute = {
  weeks: number;
  written: string[];
  kept_manual: string[];
  no_data: string[];
};

export const fetchInventoryAuto = () => req<InventoryAutoConfig>(`/api/inventory/auto`);

export const saveInventoryAuto = (enabled: boolean) =>
  req<InventoryAutoConfig>(`/api/inventory/auto`, { method: "PUT", body: JSON.stringify({ enabled }) });

/** Xem trước số tự tính của 1 tuần — KHÔNG ghi gì (để đối chiếu trước khi đồng bộ). */
export const previewInventoryAuto = (as_of: string) =>
  req<InventoryAutoPreview>(`/api/inventory/auto/preview?as_of=${as_of}`);

/** Đồng bộ NGAY 1 tuần theo số đơn vị — chạy được cả khi công tắc đang tắt, ghi đè cả số nhập tay. */
export const applyInventoryAuto = (as_of: string) =>
  req<{ written: boolean; data: InventoryAutoPreview; week: InventoryWeek }>(
    `/api/inventory/auto/apply?as_of=${as_of}`, { method: "POST" });

/** Tính lại N tuần gần nhất, giữ nguyên các tuần chuyên viên đã nhập tay. */
export const recomputeInventoryAuto = (weeks: number) =>
  req<InventoryRecompute>(`/api/inventory/auto/recompute?weeks=${weeks}`, { method: "POST" });
