/* Client ĐỀ NGHỊ SỬA SỐ LIỆU QUÁ KHỨ (15/09/2026).

   Đơn vị bị cửa sổ sửa / chốt số liệu chặn → gửi đề nghị kèm lý do; người có quyền `edit_request`
   (quản trị luôn có) xem trước/sau rồi duyệt (hệ thống mới ghi thật) hoặc từ chối.
   Hai bộ endpoint: `/api/member/edit-requests` (đơn vị) · `/api/edit-requests` (Ban duyệt). */

import { authHeaders } from "./auth-token";
import { API, apiFetch } from "./http";

const J = { "Content-Type": "application/json" };

export type EditRequestOp =
  | "daily_report" | "daily_move" | "contract_save" | "contract_delete" | "contract_delivery_type"
  | "demand_save" | "demand_delete" | "year_plan";
export type EditRequestStatus = "pending" | "approved" | "rejected" | "cancelled";
export type EditRequestStatusFilter = EditRequestStatus | "all";

export type EditRequestUnlock = { round_id: number; lock_date: string };

export interface EditRequest {
  id: number;
  company: string;
  op: EditRequestOp;
  op_label: string;
  title: string;
  target_key: string;
  dates: string[];
  payload: Record<string, unknown>;
  /** Ảnh chụp bản ghi LÚC GỬI (null = thêm mới). */
  before: Record<string, unknown> | null;
  reason: string;
  /** Câu báo chặn lúc gửi — để người duyệt biết vì sao đơn vị không tự sửa được. */
  blocked: string[];
  status: EditRequestStatus;
  requested_by: string;
  requested_by_name: string | null;
  requested_at: string;
  updated_at: string;
  reviewed_by: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  /** Các đợt chốt đã gỡ khi duyệt. */
  unlocked: EditRequestUnlock[] | null;
}

export type EditRequestCounts = Record<EditRequestStatus, number>;

export interface EditRequestPaged {
  items: EditRequest[];
  total: number;
  page: number;
  page_size: number;
  counts: EditRequestCounts;
}

export interface EditRequestDetail {
  request: EditRequest;
  /** Bản ghi HIỆN TẠI (cùng hình dạng với `before`). */
  current: Record<string, unknown> | null;
  changed_since_submit: boolean;
  /** `null` = server không kiểm được (vd tài khoản người gửi đã bị khoá). */
  still_blocked: boolean | null;
  /** Lỗi nghiệp vụ mà bấm Duyệt chắc chắn gặp (vd trùng số hợp đồng) — null = không vướng gì. */
  cannot_approve?: string | null;
  lock: { locked_until: string | null; will_unlock: EditRequestUnlock[] };
  /** Nhãn hiển thị theo khoá cuối của đường dẫn: `labels.customer_id["12"]` = tên khách. */
  labels?: Record<string, Record<string, string>>;
}

export type EditRequestAction = "create" | "update" | "delete";

/** Đề nghị THÊM bản ghi mới hay SỬA/XOÁ bản ghi đang có — suy từ ảnh chụp lúc gửi: không có bản ghi
 *  (biểu ngày: có dòng nhưng chưa có số) = thêm mới. Người duyệt cần biết để đọc đúng bảng so sánh. */
export function editRequestAction(r: Pick<EditRequest, "op" | "before">): EditRequestAction {
  if (r.op.endsWith("_delete")) return "delete";
  if (!r.before) return "create";
  return r.op === "daily_report" && r.before.fields == null ? "create" : "update";
}

export const EDIT_REQUEST_ACTION: Record<EditRequestAction, { label: string; color: string }> = {
  create: { label: "Thêm mới", color: "blue" },
  update: { label: "Sửa", color: "default" },
  delete: { label: "Xoá", color: "red" },
};

export const EDIT_REQUEST_STATUS: { value: EditRequestStatus; label: string; color: string }[] = [
  { value: "pending", label: "Chờ duyệt", color: "gold" },
  { value: "approved", label: "Đã duyệt", color: "green" },
  { value: "rejected", label: "Từ chối", color: "red" },
  { value: "cancelled", label: "Đã huỷ", color: "default" },
];

export const statusMeta = (s: EditRequestStatus) =>
  EDIT_REQUEST_STATUS.find((x) => x.value === s) ?? { value: s, label: s, color: "default" };

/** Nhãn loại thao tác cho ô lọc (nhãn chi tiết từng đề nghị lấy `op_label` server trả). */
export const EDIT_REQUEST_OPS: { value: EditRequestOp; label: string }[] = [
  { value: "daily_report", label: "Biểu Thu mua / Tồn kho" },
  { value: "daily_move", label: "Đổi ngày biểu" },
  { value: "contract_save", label: "Hợp đồng / đợt giao" },
  { value: "contract_delete", label: "Xoá hợp đồng / đợt giao" },
  { value: "contract_delivery_type", label: "Chuyển loại giao hợp đồng" },
  { value: "demand_save", label: "Nhu cầu thị trường" },
  { value: "demand_delete", label: "Xoá nhu cầu thị trường" },
  { value: "year_plan", label: "Kế hoạch năm" },
];

/** Bỏ ô lọc trống khỏi query string. */
function qs(params: Record<string, string | number | undefined | null>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

// ── Phía ĐƠN VỊ ──
export const submitEditRequest = (body: { op: EditRequestOp; payload: Record<string, unknown>; reason: string }) =>
  apiFetch<{ request: EditRequest; replaced: boolean }>("/api/member/edit-requests",
    { method: "POST", headers: J, body: JSON.stringify(body) });

export const fetchMyEditRequests = (f: { status?: EditRequestStatusFilter; page?: number; page_size?: number } = {}) =>
  apiFetch<EditRequestPaged>(`/api/member/edit-requests${qs(f)}`);

export const fetchMyEditRequest = (id: number) =>
  apiFetch<{ request: EditRequest }>(`/api/member/edit-requests/${id}`);

export const cancelMyEditRequest = (id: number) =>
  apiFetch<{ request: EditRequest }>(`/api/member/edit-requests/${id}/cancel`, { method: "POST" });

// ── Phía BAN DUYỆT ──
export type EditRequestFilter = {
  status?: EditRequestStatusFilter; company?: string; op?: EditRequestOp | ""; q?: string;
  page?: number; page_size?: number;
};

export const fetchEditRequests = (f: EditRequestFilter = {}) =>
  apiFetch<EditRequestPaged>(`/api/edit-requests${qs(f)}`);

export const fetchEditRequestPendingCount = () =>
  apiFetch<{ count: number }>("/api/edit-requests/pending-count");

export const fetchEditRequestDetail = (id: number) =>
  apiFetch<EditRequestDetail>(`/api/edit-requests/${id}`);

/** `expected_updated_at` = `updated_at` của đề nghị ĐANG HIỂN THỊ — đơn vị vừa cập nhật thì server trả 409.
 *  `accept_changed` = người duyệt đã xác nhận ghi đè khi số liệu đổi kể từ lúc gửi. */
export const approveEditRequest = (id: number, body: { note?: string; expected_updated_at: string; accept_changed?: boolean }) =>
  apiFetch<{ request: EditRequest }>(`/api/edit-requests/${id}/approve`, {
    method: "POST", headers: J,
    body: JSON.stringify({
      ...(body.note?.trim() ? { note: body.note.trim() } : {}),
      expected_updated_at: body.expected_updated_at,
      ...(body.accept_changed ? { accept_changed: true } : {}),
    }),
  });

export const rejectEditRequest = (id: number, body: { note: string; expected_updated_at: string }) =>
  apiFetch<{ request: EditRequest }>(`/api/edit-requests/${id}/reject`, {
    method: "POST", headers: J,
    body: JSON.stringify({ note: body.note.trim(), expected_updated_at: body.expected_updated_at }),
  });

/** Mở 1 file nằm trong đề nghị (hợp đồng scan, hoá đơn…). Endpoint gác quyền nên PHẢI gửi Bearer —
 *  `<a href>` trần sẽ 401 (cùng lý do với `openContractFile`). */
export async function openEditRequestFile(id: number, doc: { file: string; filename?: string | null }): Promise<void> {
  const res = await fetch(
    `${API}/api/edit-requests/${id}/file/${encodeURIComponent(doc.file)}${qs({ filename: doc.filename })}`,
    { headers: authHeaders() });
  if (!res.ok) throw new Error("Không tải được file đính kèm.");
  const url = URL.createObjectURL(await res.blob());
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
