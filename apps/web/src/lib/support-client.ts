/* Client API Hỗ trợ & Thông báo · Nhắc lịch.

   MỘT bộ endpoint cho cả hai phía — server tự nhận diện tài khoản đang đứng bên nào (`side`)
   và ép phạm vi đơn vị, nên frontend không bao giờ tự gửi danh sách đơn vị lên để lọc. */

import { API } from "./api-client";
import { authHeaders } from "./auth-token";
import type { Audience } from "./entry-types";
import { apiFetch } from "./http";

export type Side = "hq" | "unit";
/** `alert` = cảnh báo số liệu hệ thống tự gửi sau giờ chốt nhập liệu (mỗi đơn vị một tin riêng). */
export type ThreadKind = "request" | "announce" | "reminder" | "alert";
export type Attachment = { file: string; filename: string; size?: number };

export type SupportContext = {
  side: Side;
  can_write: boolean;
  units: string[];        // hq: mọi đơn vị đang hoạt động · unit: đơn vị được gán
  regions: string[];
  unread: number;
  accept_label: string;
};

export type ThreadRow = {
  id: number; company: string; kind: ThreadKind; subject: string; status: "open" | "closed";
  batch_id: string | null; created_by: string | null; created_at: string;
  last_at: string; last_side: Side; unread: boolean; message_count: number; last_body: string | null;
  // Nhóm người nhận phía đơn vị (lãnh đạo · chuyên viên theo loại nhập liệu). Dữ liệu cũ thiếu
  // hoặc rỗng = chỉ lãnh đạo — luôn đọc qua `audienceOf` (support-format.ts).
  audience?: Audience[];
};

export type BatchRow = {
  group_key: string; batch_id: string | null; sample_id: number; subject: string;
  kind: ThreadKind; created_by: string | null; created_at: string; last_at: string;
  unit_count: number; unread_count: number; open_count: number; audience?: Audience[];
};

export type SupportMessage = {
  id: number; thread_id: number; side: Side; author: string; author_name: string | null;
  body: string; files: Attachment[]; created_at: string;
};

export type Paged<T> = { rows: T[]; total: number; page: number; page_size: number };

export type Reminder = {
  id: number; title: string; body: string; files: Attachment[];
  scope: "all" | "units" | "region"; units: string[]; region: string | null;
  repeat_rule: "once" | "daily" | "weekly" | "monthly";
  next_at: string; enabled: boolean; last_sent_at: string | null;
  created_by: string | null; created_at: string; target_count?: number; audience?: Audience[];
};

const J = { "Content-Type": "application/json" };

export const fetchSupportContext = () => apiFetch<SupportContext>("/api/support/context");
export const fetchSupportUnread = () => apiFetch<{ count: number }>("/api/support/unread");

export type ThreadFilter = {
  kind?: ThreadKind | ""; status?: string; q?: string; company?: string; batch_id?: string;
  unread_only?: boolean; page?: number; page_size?: number;
};

/** Bỏ ô lọc để trống ra khỏi query — server coi tham số rỗng là "không lọc" nhưng gửi thừa thì khó đọc log. */
const qs = (filter: Record<string, unknown>): string => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(filter)) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const fetchThreads = (filter: ThreadFilter = {}) =>
  apiFetch<Paged<ThreadRow>>(`/api/support/threads${qs(filter)}`);

export const fetchBatches = (filter: { status?: string; q?: string; page?: number } = {}) =>
  apiFetch<Paged<BatchRow>>(`/api/support/batches${qs(filter)}`);

export const fetchThread = (id: number) =>
  apiFetch<{ thread: ThreadRow; messages: SupportMessage[] }>(`/api/support/threads/${id}`);

/** Phía đơn vị (lãnh đạo · chuyên viên nhập liệu) gửi yêu cầu hỗ trợ lên Tập đoàn. Người nhận
 *  trong đơn vị do server tự tính (lãnh đạo + chuyên viên cùng loại với người gửi). */
export const createRequest = (body: {
  company: string; subject: string; body: string; files: Attachment[];
}) => apiFetch<{ ok: boolean; thread_id: number }>("/api/support/requests",
  { method: "POST", headers: J, body: JSON.stringify(body) });

/** Tập đoàn gửi thông báo xuống 1 đơn vị · một nhóm · tất cả. */
export const createAnnouncement = (body: {
  subject: string; body: string; files: Attachment[];
  scope: "all" | "units" | "region"; units: string[]; region?: string | null; audience: Audience[];
}) => apiFetch<{ ok: boolean; units: string[]; threads: number }>("/api/support/announcements",
  { method: "POST", headers: J, body: JSON.stringify(body) });

export const replyThread = (id: number, body: string, files: Attachment[]) =>
  apiFetch<{ ok: boolean; message: SupportMessage }>(`/api/support/threads/${id}/reply`,
    { method: "POST", headers: J, body: JSON.stringify({ body, files }) });

export const setThreadStatus = (id: number, status: "open" | "closed") =>
  apiFetch<{ ok: boolean }>(`/api/support/threads/${id}/status`,
    { method: "PUT", headers: J, body: JSON.stringify({ status }) });

export const deleteThread = (id: number) =>
  apiFetch<{ ok: boolean }>(`/api/support/threads/${id}`, { method: "DELETE" });

// ── Nhắc lịch (chỉ Tập đoàn) ──
export const fetchReminders = () =>
  apiFetch<{ rows: Reminder[]; now: string }>("/api/support/reminders");

export type ReminderEdit = Omit<
  Reminder, "id" | "last_sent_at" | "created_by" | "created_at" | "target_count" | "audience"
> & { audience: Audience[] };

export const createReminder = (body: ReminderEdit) =>
  apiFetch<Reminder>("/api/support/reminders", { method: "POST", headers: J, body: JSON.stringify(body) });

export const updateReminder = (id: number, body: ReminderEdit) =>
  apiFetch<Reminder>(`/api/support/reminders/${id}`, { method: "PUT", headers: J, body: JSON.stringify(body) });

export const deleteReminder = (id: number) =>
  apiFetch<{ ok: boolean }>(`/api/support/reminders/${id}`, { method: "DELETE" });

export const runReminder = (id: number) =>
  apiFetch<{ ok: boolean; threads: number }>(`/api/support/reminders/${id}/run`, { method: "POST" });

// ── File đính kèm ──
/** Upload 1 file → thông tin để gắn vào tin (FormData nên KHÔNG tự đặt Content-Type). */
export async function uploadSupportFile(file: File): Promise<Attachment> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/api/support/file`, { method: "POST", headers: authHeaders(), body: form });
  if (!res.ok) {
    let msg = "Tải file lên thất bại";
    try { msg = (await res.json()).detail || msg; } catch { /* body không phải JSON */ }
    throw new Error(msg);
  }
  return (await res.json()) as Attachment;
}

/** Tải nội dung 1 đính kèm về dạng blob URL.
 *  Endpoint file có gác quyền theo đơn vị nên PHẢI gửi Bearer — `<img src>`/`<a href>` trần
 *  không gửi được token, vì vậy mọi chỗ hiển thị/tải file đều đi qua đây. */
export async function fetchAttachmentUrl(att: Attachment): Promise<string> {
  const url = `${API}/api/support/file/${encodeURIComponent(att.file)}?filename=${encodeURIComponent(att.filename)}`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error("Không tải được file đính kèm.");
  return URL.createObjectURL(await res.blob());
}

/** Tải đính kèm về máy. */
export async function downloadSupportFile(att: Attachment): Promise<void> {
  const objectUrl = await fetchAttachmentUrl(att);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = att.filename || att.file;
  a.click();
  URL.revokeObjectURL(objectUrl);
}

/** Đuôi file được nhận — khớp `attachment_store._TYPES` phía server (server mới là nơi chốt). */
export const SUPPORT_ACCEPT =
  ".pdf,.doc,.docx,.xls,.xlsx,.xml,.zip,.jpg,.jpeg,.png,.webp,.gif,.heic,.heif,.tif,.tiff";
export const SUPPORT_MAX_MB = 25;

/** Đính kèm này có phải ảnh xem thẳng được không (để hiện thumbnail thay vì dòng tên file). */
export const isImage = (att: Attachment): boolean =>
  /\.(jpg|jpeg|png|webp|gif)$/i.test(att.file);
