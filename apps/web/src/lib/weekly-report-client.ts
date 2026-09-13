/* Client API Báo cáo phân tích thị trường TUẦN (v2 — kỳ gộp 1–3 tuần).
   Hợp đồng: plans/260913-weekly-report-v2/plan.md mục A. */

import { API } from "./api-client";
import { authHeaders, onUnauthorized } from "./auth-token";
import { apiFetch } from "./http";

/** 1 cột tuần của kỳ — `weeks[0]` là tuần MỐC (liền trước kỳ báo cáo). */
export type WeekCol = {
  week_no: number; year: number; mon: string; fri: string;
  label: string;   // 'Tuần 35 (24/8 - 28/8)'
  short: string;   // 'T35'
  range: string;   // '24/8 – 28/8/2026'
};
type Num = number | null;
export type WeekTableRow = {
  exchange: string | null;
  grade: string;
  prev: Num; curr: Num; change_abs: Num; change_pct: Num;   // cặp CUỐI (tương thích v1)
  values: Num[];        // len = weeks
  changes: Num[];       // len = weeks - 1
  changes_pct: Num[];
};
export type RangeStat = {
  exchange: string | null; grade: string;
  high: Num; high_date: string | null; high_week_no: number | null; high_native: Num;
  low: Num; low_date: string | null; low_week_no: number | null; low_native: Num;
  native_unit: string | null;   // 'JPY/kg' | 'CNY/tấn' | 'US cent/kg'
};
export type FxRow = { pair: string; values: Num[]; changes: Num[]; changes_pct: Num[] };
export type MacroSection = { title: string; bullets: string[] };
export type WeeklyNarrative = {
  summary_prev: string[];
  movement: string[];
  exchange_notes: string[];
  physical_notes: string[];
  latex_notes: string[];
  macro: MacroSection[];
  forecast: string[];
  conclusion: string[];
  span_weeks?: number;
  report_note?: string[];
  exchange_table_notes?: string[];
  physical_table_notes?: string[];
  // Override III.3: CHƯA phải list = chế độ v1 (máy chủ đọc latex_prev/curr/change khi span=1);
  // đã là list (kể cả toàn null) = v2. Phần tử null/"" = dùng số tự tính.
  latex_override?: (string | null)[] | null;          // len = weeks
  latex_change_override?: (string | null)[] | null;   // len = weeks - 1
  latex_prev?: string | null;     // v1 — chỉ đọc báo cáo cũ
  latex_curr?: string | null;
  latex_change?: string | null;
};
export type WeeklyReport = {
  week_key: string; week_no: number; year: number; date_range: string;
  prev_week_no: number; prev_year: number; next_week_no: number; next_year: number;
  prev_col_label: string; curr_col_label: string;
  span_weeks: number;
  weeks: WeekCol[];
  last_week_no: number; last_year: number;
  title_label: string; span_label: string; prev_label: string;
  movement_label: string; next_label: string; list_label: string;
  exchange_rows: WeekTableRow[];
  physical_rows: WeekTableRow[];
  exchange_gaps: string[];
  physical_gaps: string[];
  range_stats: RangeStat[];
  physical_range_stats: RangeStat[];
  fx_rows: FxRow[];
  latex_bands: (string | null)[];
  latex_changes: (string | null)[];
  /** Số TỰ TÍNH III.3 theo dữ liệu hiện tại (bất kể ghi đè) — so với latex_bands để báo "đang dùng số đã lưu". */
  latex_auto_bands?: (string | null)[];
  latex_auto_changes?: (string | null)[];
  latex_prev: string | null; latex_curr: string | null; latex_change: string | null;
  narrative: WeeklyNarrative;
};
export type WeeklyReportSummary = {
  week_key: string; week_no: number; year: number;
  label: string;          // theo list_label của kỳ
  span_weeks?: number;
  updated: string | null;
};
/** Các ô viết có AI (key narrative). Phần IV dùng key `macro:<i>`. */
export type WeeklyTextKey =
  | "summary_prev" | "movement" | "exchange_notes" | "physical_notes" | "latex_notes"
  | "forecast" | "conclusion";
export type AiAssistResult = {
  paragraphs: string[]; source_urls: string[];
  warnings?: string[]; absolute_words?: string[];
};
export type WeeklyAiSections = Pick<WeeklyNarrative, WeeklyTextKey | "macro">;
export type AiAssistAllResult = {
  sections: WeeklyAiSections; source_urls: string[];
  warnings?: Record<string, string[]>; absolute_words?: Record<string, string[]>;
};

/** Soát chữ nhận định ĐÃ LƯU với bảng số hiện tại. key = field narrative | `macro:<i>` | `latex_bands`. */
export type WeeklyCheckResult = { warnings: Record<string, string[]>; count: number; summary: string };

const req = <T>(path: string, init?: RequestInit): Promise<T> =>
  apiFetch<T>(path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });

export const listWeeklyReports = () => req<WeeklyReportSummary[]>(`/api/weekly-reports`);
export const resolveWeek = (date: string) =>
  req<{ week_key: string }>(`/api/weekly-reports/resolve?date=${date}`);
export const getWeeklyReport = (weekKey: string) =>
  req<WeeklyReport>(`/api/weekly-reports/${weekKey}`);
export const saveWeeklyReport = (weekKey: string, narrative: WeeklyNarrative) =>
  req<WeeklyReport>(`/api/weekly-reports/${weekKey}`, { method: "PUT", body: JSON.stringify(narrative) });
export const deleteWeeklyReport = (weekKey: string) =>
  req<{ deleted: string }>(`/api/weekly-reports/${weekKey}`, { method: "DELETE" });
export const aiAssistWeekly = (weekKey: string, section: string) =>
  req<AiAssistResult>(`/api/weekly-reports/${weekKey}/ai-assist`, {
    method: "POST", body: JSON.stringify({ section }),
  });
export const checkWeeklyReport = (weekKey: string) =>
  req<WeeklyCheckResult>(`/api/weekly-reports/${weekKey}/check`);
export const aiAssistAllWeekly = (weekKey: string) =>
  req<AiAssistAllResult>(`/api/weekly-reports/${weekKey}/ai-assist-all`, { method: "POST" });

/** Gọi endpoint trả FILE (PDF, đính kèm) có Bearer → tải về máy. `<a href>` trần không gửi được token. */
export async function downloadAuthed(path: string, filename: string, method = "GET"): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, { method, headers: { ...authHeaders() } });
  } catch {
    throw new Error("Không kết nối được API tại " + API);
  }
  if (res.status === 401) { onUnauthorized(); throw new Error("Phiên đăng nhập đã hết hạn"); }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const b = await res.json(); detail = typeof b.detail === "string" ? b.detail : detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  // Thu hồi muộn: revoke ngay sau click làm một số trình duyệt huỷ lượt tải chưa kịp bắt đầu.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/** Xuất PDF báo cáo tuần → tải về. */
export const generateWeeklyPdf = (weekKey: string, filename: string) =>
  downloadAuthed(`/api/weekly-reports/${weekKey}/generate-pdf`, filename, "POST");

/** Tên file PDF theo hợp đồng: `Bao-cao-tuan-35-36-2026.pdf`. */
export const weeklyPdfName = (r: Pick<WeeklyReport, "span_label" | "week_no" | "year">) =>
  `Bao-cao-tuan-${(r.span_label || `${r.week_no}/${r.year}`).replace(/\//g, "-")}.pdf`;
