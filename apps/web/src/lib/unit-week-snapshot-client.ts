/* Client SNAPSHOT số liệu tuần — bản lưu cố định thu mua · tiêu thụ · tồn kho từng đơn vị.
   Xem: quyền `unit_daily` (như Báo cáo tổng hợp) · "Chụp ngay": chỉ admin (server chặn). */

import { authHeaders } from "./auth-token";
import { API, apiFetch } from "./http";
import type { PeriodReport } from "./unit-daily-client";

export type WeekInfo = {
  week_start: string; week_end: string; week_no: number; year: number; label: string;
};

/** Dòng Tổng cộng của 1 biểu: chỉ tiêu số đã cộng (giá/tỷ lệ bỏ trống) + tồn theo chủng loại. */
export type SnapshotTotals = {
  unit_count: number; reporting_units: number;
  stock_by_grade?: Record<string, number>;
  [key: string]: unknown;
};

export type SnapshotSummary = WeekInfo & {
  taken_at: string; taken_by: string; deadline_at: string;
  totals: { purchase: SnapshotTotals; consumption: SnapshotTotals };
};

export type SnapshotDetail = SnapshotSummary & { purchase: PeriodReport; consumption: PeriodReport };

export type SnapshotStatus = {
  due: WeekInfo & { deadline_at: string; taken: boolean };   // tuần gần nhất đã hết hạn nhập
  next: WeekInfo & { deadline_at: string };                 // tuần sẽ chụp kế tiếp
};

const BASE = "/api/unit-week-snapshots";

export const fetchSnapshots = () =>
  apiFetch<{ items: SnapshotSummary[]; status: SnapshotStatus }>(BASE);

export const fetchSnapshot = (weekStart: string) => apiFetch<SnapshotDetail>(`${BASE}/${weekStart}`);

export const takeSnapshotNow = () =>
  apiFetch<{ taken: boolean; week: WeekInfo }>(`${BASE}/take`, { method: "POST" });

/** Tải Excel của bản lưu (2 sheet Thu mua · Tiêu thụ - Tồn kho) — dựng từ số ĐÃ LƯU. */
export async function downloadSnapshotXlsx(w: WeekInfo): Promise<void> {
  const res = await fetch(`${API}${BASE}/${w.week_start}/excel`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Không tải được file Excel.");
  const href = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = href;
  a.download = `snapshot-so-lieu-tuan-${w.week_no}-${w.year}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 60_000);
}

/** ISO datetime → 'HH:mm ngày DD/MM/YYYY' (giờ máy người xem — ở VN là giờ Việt Nam). */
export function stampAt(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())} ngày ${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`;
}

/** Trễ quá ngần này mới gọi là "chụp sau hạn". Job chạy giờ CỐ ĐỊNH (11:10) — admin đổi giờ chốt
    sớm/muộn vài giờ thì lần chụp tự lệch vài giờ đến gần 1 ngày, không phải sự cố. Đổi giờ chốt thì
    chỉnh giờ job ở trang Lịch chạy. */
const LATE_AFTER_MS = 24 * 3_600_000;

/** Chụp trễ hơn hạn quá 24 giờ (máy chủ tắt cả ngày, hoặc lần chụp đầu tiên) → nhắc người xem. */
export const isLate = (s: Pick<SnapshotSummary, "taken_at" | "deadline_at">): boolean =>
  new Date(s.taken_at).getTime() - new Date(s.deadline_at).getTime() > LATE_AFTER_MS;
