/* Client NHÀ MÁY THÔNG MINH — chỉ số điện · nước · số bành đọc từ SCADA (AVEVA Historian).
   Xem: quyền `smart_factory` · Cấu hình kết nối: CHỈ admin (server chặn).
   Hợp đồng API: plans/260930-nha-may-thong-minh-scada/api-contract.md.
   Mọi thời điểm là giờ NHÀ MÁY dạng `YYYY-MM-DDTHH:MM:SS` (không kèm múi) → hiển thị bằng cách
   cắt chuỗi, KHÔNG đưa qua `new Date()` để khỏi lệch giờ theo máy người xem. */

import { apiFetch } from "./http";
import { downloadAuthed } from "./weekly-report-client";

export type MetricKey = "energy" | "water" | "bales";

/** partial = mốc 00:00 trống, dùng mẫu gần nhất TRONG ngày · reset = số bị giảm trong ngày
 *  (đặt lại đồng hồ / đọc lỗi) · in_progress = hôm nay. Chỉ ô `null` mới là NGÀY ĐỦ SỐ. */
export type MeterFlag = "partial" | "reset" | "no_data" | "in_progress" | null;

export type MeterCell = {
  open: number | null; open_at: string | null;
  close: number | null; close_at: string | null;
  used: number | null; flag: MeterFlag;
};

export type MetricMeta = { key: MetricKey; label: string; unit: string };

/** Một ngày: chỉ có key của các chỉ số nhà máy đã khai tag. */
export type DailyRow = {
  date: string;
  kwh_per_bale?: number | null;
  m3_per_bale?: number | null;
} & Partial<Record<MetricKey, MeterCell>>;

/** `total` cộng mọi ngày có số (kể cả hôm nay · mẫu bù); `avg_per_day` CHỈ tính các ngày đủ số
 *  (`days_complete` = số ngày cờ null) → null khi chưa có ngày nào đủ số. */
export type MetricSummary = {
  latest: number | null; latest_at: string | null;
  total: number | null; avg_per_day: number | null;
  days_with_data: number; days_complete: number;
};

export type Intensity = { kwh_per_bale: number | null; m3_per_bale: number | null };

export type DailyMeters = {
  factory: { id: number; name: string };
  date_from: string; date_to: string; fetched_at: string;
  metrics: MetricMeta[];
  rows: DailyRow[];
  summary: Partial<Record<MetricKey, MetricSummary>>;
  intensity: Intensity | null;
};

export type FactoryBrief = { id: number; name: string; metrics: MetricKey[] };

/** Cấu hình kết nối một nhà máy (mật khẩu KHÔNG bao giờ trả về — chỉ biết đã đặt hay chưa). */
export type ScadaFactory = {
  id: number; name: string; host: string; port: number;
  username: string; password_set: boolean;
  database: string; linked_server: string;
  energy_tags: string[]; water_tag: string | null; bales_tag: string | null;
  enabled: boolean; updated_at: string | null; updated_by: string | null;
};

/** Body tạo/sửa. `password` null/rỗng khi sửa = giữ mật khẩu cũ. */
export type ScadaFactoryInput = Omit<ScadaFactory, "id" | "password_set" | "updated_at" | "updated_by">
  & { password: string | null };

export type ScadaTestResult = {
  ok: boolean; detail: string;
  server_version?: string | null;
  /** Giờ máy SQL Server của SCADA — `YYYY-MM-DDTHH:MM:SS±HH:MM` (KÈM múi, khác các thời điểm khác). */
  server_time?: string | null;
  /** Điểm cần kiểm tra dù kết nối được (lệch múi giờ/đồng hồ, không có số gần đây…). */
  warnings?: string[];
  latest_at?: string | null;
  values?: { energy_kwh?: number | null; water_m3?: number | null; bales?: number | null };
  raw?: Record<string, number | null>;
};

const BASE = "/api/smart-factory";
const ADMIN = `${BASE}/admin/factories`;

const rangeQuery = (factoryId: number, from: string, to: string) =>
  new URLSearchParams({ factory_id: String(factoryId), date_from: from, date_to: to }).toString();

export const fetchFactories = () => apiFetch<{ factories: FactoryBrief[] }>(`${BASE}/factories`);

/** Số LŨY KẾ tới lúc đọc (thời gian thực) — `at` là mốc của chính số đó (giờ nhà máy). */
export type LiveMeters = {
  factory: { id: number; name: string };
  metrics: MetricMeta[];
  values: Partial<Record<MetricKey, { value: number | null; at: string | null }>>;
};

export const fetchLiveMeters = (factoryId: number) =>
  apiFetch<LiveMeters>(`${BASE}/meters/live?factory_id=${factoryId}`);

export const fetchDailyMeters = (factoryId: number, from: string, to: string) =>
  apiFetch<DailyMeters>(`${BASE}/meters/daily?${rangeQuery(factoryId, from, to)}`);

/** Tải Excel đúng nhà máy + kỳ đang xem (fetch kèm Bearer token — `window.open` sẽ bị 401). */
export const downloadDailyMetersXlsx = (factory: { id: number; name: string }, from: string, to: string) =>
  downloadAuthed(`${BASE}/meters/daily.xlsx?${rangeQuery(factory.id, from, to)}`,
    `chi-so-dien-nuoc-banh_${slug(factory.name)}_${from}_${to}.xlsx`);

export const fetchScadaFactories = () => apiFetch<{ factories: ScadaFactory[] }>(ADMIN);

const jsonBody = (method: string, body: unknown): RequestInit => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

export const createScadaFactory = (input: ScadaFactoryInput) =>
  apiFetch<{ factory: ScadaFactory }>(ADMIN, jsonBody("POST", input));

export const updateScadaFactory = (id: number, input: ScadaFactoryInput) =>
  apiFetch<{ factory: ScadaFactory }>(`${ADMIN}/${id}`, jsonBody("PUT", input));

export const deleteScadaFactory = (id: number) =>
  apiFetch<{ ok: boolean }>(`${ADMIN}/${id}`, { method: "DELETE" });

/** Luôn 200: lỗi kết nối nằm trong `ok=false` + `detail`. */
export const testScadaFactory = (id: number) =>
  apiFetch<ScadaTestResult>(`${ADMIN}/${id}/test`, { method: "POST" });

/** "Nhà máy Phú Riềng" → "nha-may-phu-rieng" (khớp cách server đặt tên file). */
function slug(s: string): string {
  return s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/gi, "d").toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "nha-may";
}
