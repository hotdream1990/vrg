/* Client gọi API FastAPI (cổng VRG 8390). Bọc fetch + types dùng chung cho UI. */

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8390";

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

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** Quét đa sàn → ghi DB → trả bản ghi + trạng thái + thông tin persist. */
export const scanPrices = (source = "all") =>
  req<ScanResult>(`/api/prices/scan?source=${encodeURIComponent(source)}`, { method: "POST" });

/** Giá mới nhất mỗi (sàn, mặt hàng) đã lưu DB (dùng khi mở trang, khỏi phải quét lại). */
export const fetchLatest = () => req<{ records: LatestRow[] }>("/api/prices/latest");

/** Chuỗi giá lịch sử cho biểu đồ. */
export const fetchHistory = (source: string, grade: string, days = 30) =>
  req<HistorySeries>(`/api/prices/history?source=${source}&grade=${grade}&days=${days}`);

export { API };
