/* Độ tươi tỷ giá — GET /api/prices/fx-health (server kiểm thẳng kho giá, độc lập trạng thái crawler). */

import { apiFetch } from "./http";

export type FxStaleItem = {
  pair: string;              // vd USD/JPY
  latest: string | null;     // ngày mới nhất có giá (YYYY-MM-DD); null = chưa có dữ liệu
  lag: number | null;        // số ngày làm việc (T2–T6) đã trễ tính tới hôm nay
};

export type FxHealth = { stale: FxStaleItem[]; checked_at: string; threshold: number };

/** Tỷ giá tự động nào đang quá cũ (cần quyền xem `auto_data`). */
export const fetchFxHealth = () => apiFetch<FxHealth>("/api/prices/fx-health");

const ddmm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

/** "USD/JPY, USD/CNY chưa cập nhật từ 02/09 (trễ 7 phiên)" — gộp các cặp cùng ngày dừng. */
export function describeStale(stale: FxStaleItem[]): string {
  const groups = new Map<string, FxStaleItem[]>();
  for (const s of stale) {
    const key = `${s.latest ?? ""}|${s.lag ?? ""}`;
    groups.set(key, [...(groups.get(key) ?? []), s]);
  }
  return [...groups.values()]
    .map((items) => {
      const pairs = items.map((s) => s.pair).join(", ");
      const { latest, lag } = items[0];
      return latest ? `${pairs} chưa cập nhật từ ${ddmm(latest)} (trễ ${lag} phiên)` : `${pairs} chưa có dữ liệu`;
    })
    .join("; ");
}
