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

/** `layout_key` khác null = nhà máy có Sơ đồ vận hành (bố cục khai sẵn ở server). */
export type FactoryBrief = { id: number; name: string; metrics: MetricKey[]; layout_key?: string | null };

/** Cấu hình kết nối một nhà máy (mật khẩu KHÔNG bao giờ trả về — chỉ biết đã đặt hay chưa). */
export type ScadaFactory = {
  id: number; name: string; host: string; port: number;
  username: string; password_set: boolean;
  database: string; linked_server: string;
  energy_tags: string[]; water_tag: string | null; bales_tag: string | null;
  /** Bố cục Sơ đồ vận hành (vd "phu_rieng") — null = nhà máy không có sơ đồ. */
  layout_key: string | null;
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

// ── Sơ đồ vận hành (mimic SCADA) — plans/260930-nha-may-thong-minh-scada/so-do-van-hanh-contract.md ──

export type PlantNodeKind =
  "mixer" | "conveyor" | "screw" | "crusher" | "tank" | "pump" | "fan" | "zone" | "motor" | "counter";

type Pt = [number, number];

/** Thiết bị trên sơ đồ: (x, y) = góc trên-trái khung w×h theo toạ độ của khu; `angle` xoay quanh tâm khung.
 *  v2 (so-do-van-hanh-contract-v2.md): `info_xy` / `temps_xy` = góc trên-trái khối nhãn + Hz/A · khối nhiệt độ
 *  (toạ độ tuyệt đối, không xoay; có thì bỏ qua `label_pos`); `variant` chọn dáng máy cán. */
export type PlantNode = {
  id: string; kind: PlantNodeKind; x: number; y: number; w: number; h: number; angle?: number;
  label: string; label_pos?: "top" | "bottom" | "left" | "right";
  metrics?: { key: string; tag: string; unit: string }[];
  status_tag?: string | null;
  temps?: { label: string; tag: string }[];
  info_xy?: Pt; temps_xy?: Pt; temps_cols?: 1 | 2;
  variant?: "mill" | "creper";
};

/** Nét trang trí: basin (bể) · pipe (đường ống theo `points`) · arrow_text (mũi tên + chữ; `text_xy` = chỗ
 *  đặt chữ, neo trái) · badge (ô chữ nhỏ viền đậm tại góc trên-trái x, y — vd "pID"). */
export type PlantDecor = {
  kind: "basin" | "pipe" | "arrow_text" | "badge";
  x?: number; y?: number; w?: number; h?: number; points?: Pt[]; text?: string; text_xy?: Pt;
};

/** `usage_box` có → vẽ bảng "Thống kê tiêu thụ trong ngày" ngay trong khung tại hình chữ nhật đó;
 *  `hidden` → khu tạm ẩn (server bỏ khỏi bố cục; web cũng lọc cho chắc). */
export type PlantArea = {
  key: string; label: string; width: number; height: number; hidden?: boolean;
  nodes: PlantNode[]; decor?: PlantDecor[]; links?: [string, string][];
  usage_box?: { x: number; y: number; w: number; h: number };
};

export type PlantLayout = {
  key: string;
  power: { label: string; unit: string; tag: string }[];
  areas: PlantArea[];
};

/** Số mới nhất của một tag — `at` giờ nhà máy; tag chưa có số thì vắng mặt hoặc `value` null. */
export type PlantReading = { value: number | null; at: string | null };
export type PlantValues = Record<string, PlantReading>;

export const fetchPlantLayout = (factoryId: number) =>
  apiFetch<{ factory: { id: number; name: string }; layout: PlantLayout }>(
    `${BASE}/plant/layout?factory_id=${factoryId}`);

/** Số mới nhất của mọi tag trong khu + tag điện (`power`). `fetched_at` = giờ VN của máy chủ app lúc trả
 *  lời (cùng khuôn `at`) — so với `at` mới nhất để biết số đã cũ (SCADA ngừng ghi). */
export const fetchPlantLive = (factoryId: number, area: string) =>
  apiFetch<{ area: string; values: PlantValues; fetched_at?: string | null }>(
    `${BASE}/plant/live?${new URLSearchParams({ factory_id: String(factoryId), area }).toString()}`);

/** Các bố cục Sơ đồ vận hành server có sẵn (chỉ admin) — cho ô chọn trong form cấu hình. */
export const fetchPlantLayouts = () =>
  apiFetch<{ layouts: { key: string; label: string }[] }>(`${BASE}/admin/layouts`);

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
