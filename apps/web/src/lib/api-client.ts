/* Client gọi API FastAPI (cổng VRG 8390). Bọc fetch + types dùng chung cho UI. */

import { API, apiFetch } from "./http";

export type PriceRow = {
  source: string;
  grade: string;
  price: number;
  currency: string;
  unit: string;
  price_type: string;
  as_of: string;
  contract?: string | null;
};

export type LatestRow = PriceRow & { ingested_at?: string };

export type SourceStatus = { source: string; status: string; count: number; note?: string | null };

export type ScanResult = {
  records: PriceRow[];
  sources: SourceStatus[];
  persisted: number;
  run_id: number | null;
  db: string;
};

export type HistorySeries = {
  source: string;
  grade: string;
  points: { as_of: string; price: number }[];
};

// ── Bảng giá thành phần (native · tỷ giá · USD/T) + tỷ giá ──

export type ExchangeComponent = {
  exchange: string;
  grade: string;
  native_price: number;
  native_unit: string;
  fx_pair: string | null;
  fx_rate: number | null;
  usd_tonne: number | null;
  as_of: string;
};

export type FxRateItem = { pair: string; rate: number; as_of: string | null };

export type PriceBoard = {
  exchanges: ExchangeComponent[];
  fx: FxRateItem[];
  ingested_at: string | null;
};

/** Bảng giá thành phần per sàn + danh sách tỷ giá (dashboard Quét Đa sàn). */
export const fetchBoard = () => req<PriceBoard>("/api/prices/board");

// ── Lưới "Bảng tính giá" (giống sheet mẫu VRG) ──

export type SheetEdit = {
  source: string; grade: string; price_type: string;
  currency: string; unit: string; scale: number; field: "native" | "usd";
};
export type SheetCol = {
  key: string; grade: string; label: string;
  show_native: boolean; native_label?: string; native_unit?: string;
  show_fx: boolean; fx_pair?: string; edit: SheetEdit;
};
export type SheetGroup = { exchange: string; label: string; cols: SheetCol[] };
export type SheetCell = { usd: number | null; native?: number | null; fx_rate?: number | null };
export type SheetRow = {
  as_of: string;
  cells: Record<string, SheetCell>;
  fx: Record<string, number | null>;
};
export type PriceSheet = { groups: SheetGroup[]; fx_pairs: string[]; rows: SheetRow[] };

/** Lưới giá theo ngày × sàn (Native·Tỷ giá·USD) + tỷ giá — giống file mẫu. Lọc khoảng ngày tùy chọn. */
export const fetchSheet = (opts: { days?: number; dateFrom?: string; dateTo?: string } = {}) => {
  const p = new URLSearchParams();
  if (opts.dateFrom) p.set("date_from", opts.dateFrom);
  if (opts.dateTo) p.set("date_to", opts.dateTo);
  if (!opts.dateFrom && !opts.dateTo) p.set("days", String(opts.days ?? 30));
  return req<PriceSheet>(`/api/prices/sheet?${p}`);
};

// ── Giá mủ nguyên liệu (giá thu mua mủ nước theo công ty × ngày) ──

export type PurchaseSheet = {
  companies: string[];
  dates: string[];                                    // mới nhất trước
  values: Record<string, Record<string, number>>;     // values[company][date] = đồng/độ TSC
};

/** Lưới giá thu mua mủ nước (công ty × ngày). Lọc khoảng ngày tùy chọn. */
export const fetchPurchaseSheet = (dateFrom?: string, dateTo?: string) => {
  const p = new URLSearchParams();
  if (dateFrom) p.set("date_from", dateFrom);
  if (dateTo) p.set("date_to", dateTo);
  return req<PurchaseSheet>(`/api/prices/purchase-sheet?${p}`);
};

/** Xoá toàn bộ giá thu mua mủ nước của 1 ngày. */
export const deletePurchaseDate = (as_of: string) =>
  req<{ deleted: number }>(`/api/prices/purchase?as_of=${as_of}`, { method: "DELETE" });

export type PhysicalSheet = {
  grades: string[];
  dates: string[];                                    // mới nhất trước
  values: Record<string, Record<string, number>>;     // values[grade][date]
};

/** Lưới giá Physical (giao ngay): grade × ngày. Lọc khoảng ngày tùy chọn. */
export const fetchPhysicalSheet = (dateFrom?: string, dateTo?: string) => {
  const p = new URLSearchParams();
  if (dateFrom) p.set("date_from", dateFrom);
  if (dateTo) p.set("date_to", dateTo);
  return req<PhysicalSheet>(`/api/prices/physical-sheet?${p}`);
};

/** Xoá toàn bộ giá physical của 1 ngày. */
export const deletePhysicalDate = (as_of: string) =>
  req<{ deleted: number }>(`/api/prices/physical?as_of=${as_of}`, { method: "DELETE" });

const req = apiFetch;

/** Quét đa sàn → ghi DB → trả bản ghi + trạng thái + thông tin persist. */
export const scanPrices = (source = "all") =>
  req<ScanResult>(`/api/prices/scan?source=${encodeURIComponent(source)}`, { method: "POST" });

/** Giá mới nhất mỗi (sàn, mặt hàng) đã lưu DB (dùng khi mở trang, khỏi phải quét lại). */
export const fetchLatest = () => req<{ records: LatestRow[] }>("/api/prices/latest");

export type CrawlRun = {
  id: number;
  started_at: string;
  finished_at: string | null;
  sources: string | null;
  status: string;
  rows: number;
  error: string | null;
};

/** Nhật ký các lần quét gần nhất (quét thủ công + cron). */
export const fetchCrawlRuns = (limit = 20) =>
  req<{ runs: CrawlRun[] }>(`/api/prices/crawl-runs?limit=${limit}`);

export type ConfigGroup = { id: string; label: string };
export type ConfigItem = {
  key: string;
  label: string;
  secret: boolean;
  placeholder: string;
  group: string;
  options: string[] | null;
  provider: string | null;
  is_set: boolean;
  display: string | null;
};
export type ConfigResponse = { groups: ConfigGroup[]; config: ConfigItem[] };

/** Cấu hình hệ thống (admin) — secret đã được server mask, không trả giá trị thật. */
export const fetchConfig = () => req<ConfigResponse>("/api/config");

/** Danh sách model cho dropdown (OpenAI lấy thật từ tài khoản nếu đã đặt key). */
export const fetchLlmModels = () => req<{ openai: string[] }>("/api/config/llm-models");

/** Lưu cấu hình (chỉ gửi ô đã nhập; ô trống = giữ nguyên). */
export const saveConfig = (updates: Record<string, string>) =>
  req<ConfigResponse & { updated: number }>("/api/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });

export type MsTestResult = { ok: boolean; stage: string; message: string; screenshot?: string };

/** Chạy thử đăng nhập marketscreener bằng tài khoản ĐÃ LƯU (mất ~30–60s). */
export const testMarketscreener = () =>
  req<MsTestResult>("/api/config/marketscreener/test", { method: "POST" });

export type ScheduleJob = {
  name: string;
  label: string;
  purpose: string | null;
  hour: number;
  minute: number;
  enabled: boolean;
  last_run: CrawlRun | null;
  next_run: string | null;
};

/** Lịch chạy job định kỳ (scheduler trong app). */
export const fetchSchedules = () => req<{ jobs: ScheduleJob[] }>("/api/schedules");

export const updateSchedule = (name: string, body: { hour: number; minute: number; enabled: boolean }) =>
  req<{ ok: boolean }>(`/api/schedules/${name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

/** Chạy 1 job ngay (thủ công). */
export const runSchedule = (name: string) =>
  req<ScanResult>(`/api/schedules/${name}/run`, { method: "POST" });

/** Chuỗi giá lịch sử cho biểu đồ. */
export const fetchHistory = (source: string, grade: string, days = 30) =>
  req<HistorySeries>(`/api/prices/history?source=${source}&grade=${grade}&days=${days}`);

export type BackfillResult = {
  source: string;
  days: number;
  records: number;
  persisted: number;
  run_id: number | null;
  db: string;
};

/** Nạp lịch sử settlement (shfe/tocom) vào DB để vẽ chart thật. */
export const backfillPrices = (source = "shfe", days = 90) =>
  req<BackfillResult>(`/api/prices/backfill?source=${source}&days=${days}`, { method: "POST" });

// ── Quản lý bản ghi giá (đa sàn) ──

export type PriceRecord = {
  as_of: string;
  source: string;
  grade: string;
  contract: string;
  price_type: string;
  price: number;
  currency: string;
  unit: string;
  ingested_at?: string;
};

const reqDetail = apiFetch;

export type RecordQuery = {
  source?: string; grade?: string; dateFrom?: string; dateTo?: string;
  page?: number; pageSize?: number;
};
export type RecordPage = {
  records: PriceRecord[]; total: number; page: number; page_size: number;
};

/** Liệt kê bản ghi giá: lọc nguồn/chỉ số/khoảng ngày + phân trang. */
export const listRecords = (q: RecordQuery = {}) => {
  const p = new URLSearchParams();
  if (q.source) p.set("source", q.source);
  if (q.grade) p.set("grade", q.grade);
  if (q.dateFrom) p.set("date_from", q.dateFrom);
  if (q.dateTo) p.set("date_to", q.dateTo);
  p.set("page", String(q.page ?? 1));
  p.set("page_size", String(q.pageSize ?? 25));
  return reqDetail<RecordPage>(`/api/prices/records?${p}`);
};

/** Thêm/sửa 1 bản ghi giá (khóa: as_of+source+grade+contract+price_type). */
export const upsertRecord = (rec: Omit<PriceRecord, "ingested_at">) =>
  reqDetail<{ ok: boolean }>(`/api/prices/records`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(rec),
  });

/** Xóa 1 bản ghi giá theo khóa. */
export const deleteRecord = (
  k: Pick<PriceRecord, "as_of" | "source" | "grade" | "contract" | "price_type">,
) => {
  const p = new URLSearchParams({
    as_of: k.as_of, source: k.source, grade: k.grade,
    contract: k.contract ?? "", price_type: k.price_type,
  });
  return reqDetail<{ deleted: boolean }>(`/api/prices/records?${p}`, { method: "DELETE" });
};

export { API };
