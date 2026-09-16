/* Client API Lịch sử truy cập.
   Chiều GHI (báo "vừa vào trang nào") cố ý KHÔNG dùng `apiFetch`:
     - `apiFetch` gặp 401 sẽ đá người dùng về /login — một lời báo hỏng không được phép làm thế;
     - mọi lệnh khác GET của `apiFetch` phát `DATA_SAVED_EVENT` → mỗi lần chuyển màn lại kích hoạt
       bảng nhắc việc tải lại, hoàn toàn thừa.
   Chiều ĐỌC là màn tra cứu của quản trị nên dùng `apiFetch` như mọi màn khác. */

import { authHeaders } from "./auth-token";
import { API, apiFetch } from "./http";

export type AccessEntry = {
  id: number;
  at: string;                 // ISO datetime
  username: string;
  role: string;
  on_behalf: string;          // admin đang đăng nhập hộ (rỗng = phiên bình thường)
  event: string;              // login | login_failed | page
  event_label: string;
  path: string;
  label: string;              // tên trang tiếng Việt (thiếu thì là đường dẫn)
  company: string;
  ip: string;
  user_agent: string;
};

export type AccessSummaryRow = {
  username: string;
  role: string;
  company: string;
  last_seen: string | null;
  last_login: string | null;
  logins: number;
  failed_logins: number;
  page_views: number;
  active_days: number;
  distinct_pages: number;
  top_page: string;
  top_page_views: number;
};

export type AccessTopPage = { path: string; label: string; views: number; users: number };

export type AccessPage = { items: AccessEntry[]; total: number; page: number; page_size: number };
export type AccessSummary = { items: AccessSummaryRow[]; top_pages: AccessTopPage[] };

export type AccessMeta = {
  events: { key: string; label: string }[];
  roles: { key: string; label: string }[];
  users: string[];
  units: string[];
};

export type AccessFilters = {
  date_from?: string;
  date_to?: string;
  username?: string;
  role?: string;
  event?: string;
  company?: string;
  q?: string;
  page?: number;
  page_size?: number;
};

function query(filters: AccessFilters, skip: string[] = []): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (skip.includes(k) || v === undefined || v === null || v === "") continue;
    qs.set(k, String(v));
  }
  return qs.toString();
}

/** Báo "vừa vào trang này" — bắn rồi quên: mọi lỗi đều nuốt, không hiện gì cho người dùng. */
export function trackPageView(path: string): void {
  try {
    void fetch(`${API}/api/access-log`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ path }),
      keepalive: true,            // vẫn gửi xong khi người dùng vừa bấm sang trang khác
    }).catch(() => undefined);
  } catch {
    /* không có mạng / trình duyệt chặn — bỏ qua, ghi vết không quan trọng bằng việc đang làm */
  }
}

export const fetchAccessMeta = () => apiFetch<AccessMeta>(`/api/access-log/meta`);

export const fetchAccessSummary = (f: AccessFilters) =>
  apiFetch<AccessSummary>(`/api/access-log/summary?${query(f, ["page", "page_size", "event"])}`);

export const fetchAccessLog = (f: AccessFilters) =>
  apiFetch<AccessPage>(`/api/access-log?${query(f)}`);

/** Tải Excel đúng bộ lọc đang xem (gửi kèm Bearer token nên phải fetch rồi lưu blob). */
export async function downloadAccessXlsx(f: AccessFilters): Promise<void> {
  const res = await fetch(`${API}/api/access-log/export?${query(f, ["page", "page_size"])}`,
    { headers: authHeaders() });
  if (!res.ok) throw new Error("Không xuất được Excel — thử lại hoặc thu hẹp bộ lọc.");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "lich-su-truy-cap.xlsx";
  a.click();
  URL.revokeObjectURL(url);
}
