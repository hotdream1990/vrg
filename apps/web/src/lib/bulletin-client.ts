/* Client API cho Bản tin ngày — gọi bulletin endpoints. */

import { API } from "./api-client";
import { authHeaders, onUnauthorized } from "./auth-token";
import { apiFetch } from "./http";

// ── Types ──

export type WorldPriceItem = {
  exchange: string;
  grade: string;
  unit: string;
  price_prev: number | null;
  price_curr: number | null;
  change_abs: number | null;
  change_pct: number | null;
};

export type PhysicalPriceItem = {
  grade: string;
  price_prev: number | null;
  price_curr: number | null;
  change_abs: number | null;
  change_pct: number | null;
};

export type VrgFloorItem = {
  grade: string;
  fob_usd: number | null;
  domestic_vnd: number | null;
};

export type RawMaterialRegion = {
  region: string;            // tên công ty thành viên VRG
  price: number | null;      // đồng/độ TSC
  unit?: string;
  price_text: string;        // số đã format (không kèm đơn vị)
};

export type SectionStatus = {
  section: string;
  source: "db" | "manual" | "empty";
  description: string;
};

export type BulletinDraft = {
  report_date: string;
  prev_date: string;
  world_prices: WorldPriceItem[];
  physical_prices: PhysicalPriceItem[];
  vrg_floor_prev_label: string;
  vrg_floor_curr_label: string;
  vrg_floor_prev: VrgFloorItem[];
  vrg_floor_curr: VrgFloorItem[];
  raw_materials: RawMaterialRegion[];
  exchange_summary: string[];
  physical_summary: string;
  market_analysis: string[];
  source_urls: string[];
  data_sources: SectionStatus[];
};

export type BulletinDraftUpdate = {
  vrg_floor_prev_label?: string;
  vrg_floor_curr_label?: string;
  vrg_floor_prev?: VrgFloorItem[];
  vrg_floor_curr?: VrgFloorItem[];
  raw_materials?: RawMaterialRegion[];
  exchange_summary?: string[];
  physical_summary?: string;
  market_analysis?: string[];
  source_urls?: string[];
};

// ── API calls ──

const req = apiFetch;

/** Tạo draft mới (đọc giá thật từ DB). */
export const createDraft = (dateStr?: string, crawl = true) => {
  const params = new URLSearchParams();
  if (dateStr) params.set("report_date", dateStr);
  if (!crawl) params.set("crawl", "false");
  return req<BulletinDraft>(`/api/bulletins/draft?${params}`, { method: "POST" });
};

/** Lấy draft hiện có. */
export const getDraft = (dateStr?: string) => {
  const params = new URLSearchParams();
  if (dateStr) params.set("report_date", dateStr);
  return req<BulletinDraft>(`/api/bulletins/draft?${params}`);
};

/** Cập nhật phần editable. */
export const updateDraft = (updates: BulletinDraftUpdate, dateStr?: string) => {
  const params = new URLSearchParams();
  if (dateStr) params.set("report_date", dateStr);
  return req<BulletinDraft>(`/api/bulletins/draft?${params}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
};

/** AI lấy tin thị trường (vietnambiz) + viết các đoạn phân tích cho Section IV. */
export const generateMarketAnalysis = () =>
  req<{ paragraphs: string[]; source_url: string }>("/api/bulletins/market-analysis", {
    method: "POST",
  });

/** POST endpoint trả file → tải về trình duyệt. */
async function downloadBlob(path: string, filename: string): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, { method: "POST", headers: { ...authHeaders() } });
  } catch {
    throw new Error("Không kết nối được API. Kiểm tra API đang chạy ở " + API);
  }
  if (res.status === 401) { onUnauthorized(); throw new Error("Phiên đăng nhập đã hết hạn"); }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const body = await res.json(); detail = body.detail || detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** Xuất PPTX → tải về. */
export const generatePptx = (dateStr?: string) => {
  const p = new URLSearchParams();
  if (dateStr) p.set("report_date", dateStr);
  return downloadBlob(`/api/bulletins/generate?${p}`, `Ban-tin-ngay-${dateStr || "latest"}.pptx`);
};

/** Xuất PDF (có trang đầu/cuối + header/footer + nhảy trang) → tải về. */
export const generatePdf = (dateStr?: string) => {
  const p = new URLSearchParams();
  if (dateStr) p.set("report_date", dateStr);
  return downloadBlob(`/api/bulletins/generate-pdf?${p}`, `Ban-tin-ngay-${dateStr || "latest"}.pdf`);
};

// ── Published bulletins (đã xuất) ──

export type PublishedBulletin = {
  filename: string;
  report_date: string | null;
  size: number;
  modified: string;
  download_url: string;
};

/** Liệt kê bản tin đã xuất (file PPTX trong data/bulletins/). */
export const listPublished = () =>
  req<{ bulletins: PublishedBulletin[] }>(`/api/bulletins/published`);

/** URL tải 1 bản tin đã xuất. */
export const publishedDownloadUrl = (filename: string) =>
  `${API}/api/bulletins/published/${encodeURIComponent(filename)}`;

/** Chi tiết 1 bản tin đã xuất (snapshot JSON, fallback dựng từ DB). */
export const getPublishedDetail = (filename: string) =>
  req<BulletinDraft>(`/api/bulletins/published/${encodeURIComponent(filename)}/detail`);

// ── Image settings ──

export type ImageSlot = {
  slot: string;
  label: string;
  default_url: string | null;
  custom_url: string | null;
  active_source: "default" | "custom" | null;
  active_url: string | null;
};

/** Liệt kê tất cả image slots. */
export const listImages = () =>
  req<{ images: ImageSlot[] }>(`/api/bulletins/images`);

/** Upload hình mới cho slot. */
export const uploadImage = async (slot: string, file: File): Promise<ImageSlot[]> => {
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API}/api/bulletins/images/${slot}`, { method: "POST", headers: { ...authHeaders() }, body: form });
  } catch {
    throw new Error("Không kết nối được API");
  }
  if (res.status === 401) { onUnauthorized(); throw new Error("Phiên đăng nhập đã hết hạn"); }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const b = await res.json(); detail = b.detail || detail; } catch {}
    throw new Error(detail);
  }
  // Reload full list after upload
  const list = await listImages();
  return list.images;
};

/** Xóa custom image → revert về default. */
export const deleteCustomImage = async (slot: string): Promise<ImageSlot[]> => {
  await req<unknown>(`/api/bulletins/images/${slot}`, { method: "DELETE" });
  const list = await listImages();
  return list.images;
};

/** Get full image URL for a slot. */
export const getImageUrl = (slot: string, source: "active" | "default" | "custom" = "active") =>
  `${API}/api/bulletins/images/${slot}?source=${source}&t=${Date.now()}`;

