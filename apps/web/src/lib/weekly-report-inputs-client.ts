/* Client đầu vào hỗ trợ viết Báo cáo tuần: tài liệu đính kèm · chỉ số tài chính · tin trong kỳ.
   Hợp đồng: plans/260913-weekly-report-v2/plan.md mục B (Đính kèm, Đầu vào thị trường). */

import { API } from "./api-client";
import { authHeaders, onUnauthorized } from "./auth-token";
import { apiFetch } from "./http";
import { downloadAuthed } from "./weekly-report-client";

export type AttachmentKind = "anrpc" | "other";
export type WeeklyAttachment = {
  id: number;
  week_key: string;
  filename: string;
  size: number;
  kind: AttachmentKind;
  pages: number | null;
  text_chars: number;
  summary: string | null;
  uploaded_by: string | null;
  created_at: string | null;
};
export type PointValue = { value: number | null; date: string } | null;   // date 'dd/mm'
export type WeeklyIndicator = {
  source_id: number | null;
  name: string;
  role: string | null;
  url: string | null;
  symbol: string | null;
  values: (number | null)[];
  changes: (number | null)[];
  changes_pct: (number | null)[];
  last_closes?: unknown;
  high: PointValue;
  low: PointValue;
  error: string | null;
};
export type PeriodArticle = { url: string; title: string; published: string };

export const ATTACHMENT_ACCEPT = ".pdf,.docx";
const J = { "Content-Type": "application/json" };
const base = (weekKey: string) => `/api/weekly-reports/${weekKey}/attachments`;

export const listAttachments = (weekKey: string) => apiFetch<WeeklyAttachment[]>(base(weekKey));

/** Upload multipart — KHÔNG tự đặt Content-Type (trình duyệt tự gắn boundary). */
export async function uploadAttachment(weekKey: string, file: File, kind: AttachmentKind): Promise<WeeklyAttachment> {
  const form = new FormData();
  form.append("file", file);
  form.append("kind", kind);
  let res: Response;
  try {
    res = await fetch(`${API}${base(weekKey)}`, { method: "POST", headers: authHeaders(), body: form });
  } catch {
    throw new Error(`Không kết nối được máy chủ (${API}) — kiểm tra mạng hoặc thử lại.`);
  }
  if (res.status === 401) { onUnauthorized(); throw new Error("Phiên đăng nhập đã hết hạn — vui lòng đăng nhập lại."); }
  if (!res.ok) {
    let msg = "Tải file lên thất bại";
    try { const b = await res.json(); if (typeof b.detail === "string") msg = b.detail; } catch { /* không phải JSON */ }
    throw new Error(msg);
  }
  return (await res.json()) as WeeklyAttachment;
}

export const patchAttachment = (weekKey: string, id: number, body: { kind?: AttachmentKind; summary?: string }) =>
  apiFetch<WeeklyAttachment>(`${base(weekKey)}/${id}`, { method: "PATCH", headers: J, body: JSON.stringify(body) });

export const deleteAttachment = (weekKey: string, id: number) =>
  apiFetch<unknown>(`${base(weekKey)}/${id}`, { method: "DELETE" });

export const attachmentText = (weekKey: string, id: number) =>
  apiFetch<{ text: string }>(`${base(weekKey)}/${id}/text`);

export const summarizeAttachment = (weekKey: string, id: number) =>
  apiFetch<{ summary: string; warnings: string[] }>(`${base(weekKey)}/${id}/summarize`, { method: "POST" });

export const downloadAttachment = (weekKey: string, att: WeeklyAttachment) =>
  downloadAuthed(`${base(weekKey)}/${att.id}/file`, att.filename);

export const getWeeklyIndicators = (weekKey: string, span?: number) =>
  apiFetch<{ indicators: WeeklyIndicator[] }>(
    `/api/weekly-reports/${weekKey}/indicators${span ? `?span=${span}` : ""}`,
  );

export const getWeeklyNews = (weekKey: string) =>
  apiFetch<{ articles: PeriodArticle[] }>(`/api/weekly-reports/${weekKey}/news`);
