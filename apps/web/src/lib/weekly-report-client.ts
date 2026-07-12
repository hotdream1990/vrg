/* Client API Báo cáo phân tích thị trường TUẦN. */

import { API } from "./api-client";
import { authHeaders, onUnauthorized } from "./auth-token";
import { apiFetch } from "./http";

export type WeekTableRow = {
  exchange: string | null;
  grade: string;
  prev: number | null;
  curr: number | null;
  change_abs: number | null;
  change_pct: number | null;
};
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
  latex_prev: string | null;
  latex_curr: string | null;
  latex_change: string | null;
};
export type WeeklyReport = {
  week_key: string;
  week_no: number;
  year: number;
  date_range: string;
  prev_week_no: number;
  prev_year: number;
  next_week_no: number;
  next_year: number;
  prev_col_label: string;
  curr_col_label: string;
  exchange_rows: WeekTableRow[];
  physical_rows: WeekTableRow[];
  latex_prev: string | null;
  latex_curr: string | null;
  latex_change: string | null;
  narrative: WeeklyNarrative;
};
export type WeeklyReportSummary = {
  week_key: string;
  week_no: number;
  year: number;
  label: string;
  updated: string | null;
};
export type AiAssistResult = { paragraphs: string[]; source_urls: string[] };
export type WeeklyAiSections = Omit<WeeklyNarrative, "latex_prev" | "latex_curr" | "latex_change">;
export type AiAssistAllResult = { sections: WeeklyAiSections; source_urls: string[] };

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
export const aiAssistAllWeekly = (weekKey: string) =>
  req<AiAssistAllResult>(`/api/weekly-reports/${weekKey}/ai-assist-all`, { method: "POST" });

/** Xuất PDF báo cáo tuần → tải về. */
export async function generateWeeklyPdf(weekKey: string, filename: string): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API}/api/weekly-reports/${weekKey}/generate-pdf`, {
      method: "POST", headers: { ...authHeaders() },
    });
  } catch {
    throw new Error("Không kết nối được API tại " + API);
  }
  if (res.status === 401) { onUnauthorized(); throw new Error("Phiên đăng nhập đã hết hạn"); }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const b = await res.json(); detail = b.detail || detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
