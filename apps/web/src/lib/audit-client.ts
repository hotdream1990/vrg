/* Client API Nhật ký hoạt động (audit log) — chỉ ĐỌC (vết do backend tự ghi khi có thay đổi). */

import { authHeaders } from "./auth-token";
import { API, apiFetch } from "./http";

export type AuditEntry = {
  id: number;
  at: string;                       // ISO datetime
  actor: string;                    // username · 'system' · 'public:<đơn vị>'
  actor_role: string;
  on_behalf: string;                // admin đang đăng nhập hộ (rỗng = phiên bình thường)
  entity: string;
  entity_label: string;
  action: string;                   // create | update | delete | scan
  action_label: string;
  entity_key: string;
  as_of: string | null;             // ngày số liệu
  company: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip: string;
  note: string;
};

export type AuditPage = { items: AuditEntry[]; total: number; page: number; page_size: number };

export type AuditMeta = {
  entities: { key: string; label: string }[];
  actions: { key: string; label: string }[];
  actors: string[];
  units: string[];
};

export type AuditFilters = {
  date_from?: string;
  date_to?: string;
  actor?: string;
  entity?: string;
  action?: string;
  company?: string;
  q?: string;
  page?: number;
  page_size?: number;
};

export const fetchAuditMeta = () => apiFetch<AuditMeta>(`/api/audit/meta`);

export function fetchAuditLog(filters: AuditFilters): Promise<AuditPage> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  return apiFetch<AuditPage>(`/api/audit?${qs.toString()}`);
}

/** Tải Excel đúng bộ lọc đang xem (gửi kèm Bearer token nên phải fetch rồi lưu blob). */
export async function downloadAuditXlsx(filters: AuditFilters): Promise<void> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (k !== "page" && k !== "page_size" && v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  const res = await fetch(`${API}/api/audit/export?${qs.toString()}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Không xuất được Excel — thử lại hoặc thu hẹp bộ lọc.");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "nhat-ky-hoat-dong.xlsx";
  a.click();
  URL.revokeObjectURL(url);
}
