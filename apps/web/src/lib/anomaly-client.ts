/* Client API "Cảnh báo bất thường" (chỉ admin) — quét số liệu đơn vị thành viên từ đầu năm tới
   ngày chốt và gom các dấu hiệu sai: nhập sai đơn vị tính, chưa nộp, thiếu đơn giá, doanh thu vô lý…

   Backend trả cả ĐỊNH NGHĨA CỘT của từng nhóm (`columns`) nên màn hình dựng bảng động —
   thêm luật cảnh báo mới ở server là web hiện được ngay, không phải sửa frontend. */

import { authHeaders } from "./auth-token";
import { API, apiFetch } from "./http";
import { isoDate } from "./date";

const BASE = "/api/anomalies";

/** Mức nghiêm trọng của một nhóm cảnh báo (đặt ở server, web chỉ hiển thị). */
export type AnomalySeverity = "high" | "medium" | "low";

/** Một cột của bảng cảnh báo — `key` là tên trường trong mỗi dòng `rows`. */
export type AnomalyColumn = { key: string; label: string };

/** Một dòng cảnh báo: tập trường tự do, khớp theo `key` của `columns`. */
export type AnomalyRow = Record<string, unknown>;

export type AnomalyGroup = {
  key: string;
  label: string;
  desc: string;
  severity: AnomalySeverity;
  count: number;
  units: number;
  columns: AnomalyColumn[];
  rows: AnomalyRow[];
};

export type AnomalySummary = {
  total: number;
  high: number;
  medium: number;
  low: number;
  units: number;
};

export type AnomalyReport = {
  date_from: string;
  date_to: string;
  summary: AnomalySummary;
  thresholds: Record<string, number>;
  groups: AnomalyGroup[];
};

/** Một ngưỡng cấu hình được: giá trị đang áp dụng + giá trị mặc định để khôi phục. */
export type AnomalyConfigItem = {
  key: string;
  label: string;
  hint: string;
  value: number;
  default: number;
};

/** Khoảng quét mặc định: 01/01 năm nay → HÔM QUA (hôm nay chưa chốt, đơn vị còn đang nhập). */
export function defaultAnomalyRange(today = new Date()): { from: string; to: string } {
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  return { from: `${today.getFullYear()}-01-01`, to: isoDate(yesterday) };
}

export function fetchAnomalies(from: string, to: string): Promise<AnomalyReport> {
  const qs = new URLSearchParams({ date_from: from, date_to: to });
  return apiFetch<AnomalyReport>(`${BASE}?${qs.toString()}`);
}

export const fetchAnomalyConfig = (): Promise<AnomalyConfigItem[]> =>
  apiFetch<AnomalyConfigItem[]>(`${BASE}/config`);

export const saveAnomalyConfig = (values: Record<string, number>): Promise<unknown> =>
  apiFetch<unknown>(`${BASE}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ values }),
  });

/** Tải Excel đúng khoảng đang xem. Phải fetch kèm Bearer token rồi lưu blob —
 *  `window.open` không gắn được header nên server sẽ trả 401. */
export async function downloadAnomalyXlsx(from: string, to: string): Promise<void> {
  const qs = new URLSearchParams({ date_from: from, date_to: to });
  const res = await fetch(`${API}${BASE}/export.xlsx?${qs.toString()}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Không xuất được Excel — thử lại hoặc thu hẹp khoảng ngày.");
  const href = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = href;
  a.download = `canh-bao-bat-thuong-${from}-den-${to}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(href);
}
