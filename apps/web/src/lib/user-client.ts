/* Client API quản trị người dùng (app_user) — chỉ admin. */

import { API } from "./api-client";
import { authHeaders, onUnauthorized } from "./auth-token";

export type AppUser = {
  username: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try { res = await fetch(`${API}${path}`, { ...init, headers: { ...authHeaders(), ...(init?.headers ?? {}) } }); }
  catch { throw new Error("Không kết nối được API (" + API + ")"); }
  if (res.status === 401) { onUnauthorized(); throw new Error("Phiên đăng nhập đã hết hạn"); }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const b = await res.json(); msg = b.detail || msg; } catch { /* ignore */ }
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

const J = { "Content-Type": "application/json" };

/** Danh sách tất cả tài khoản. */
export const listUsers = () => req<AppUser[]>(`/api/users`);

/** Tạo tài khoản mới. */
export const createUser = (body: { username: string; password: string; full_name?: string; role?: string }) =>
  req<AppUser>(`/api/users`, { method: "POST", headers: J, body: JSON.stringify(body) });

/** Cập nhật họ tên / vai trò / trạng thái. */
export const updateUser = (username: string, body: { full_name?: string | null; role?: string; is_active?: boolean }) =>
  req<AppUser>(`/api/users/${encodeURIComponent(username)}`, { method: "PUT", headers: J, body: JSON.stringify(body) });

/** Đặt lại mật khẩu (không cần mật khẩu cũ). */
export const resetPassword = (username: string, new_password: string) =>
  req<{ detail: string }>(`/api/users/${encodeURIComponent(username)}/reset-password`,
    { method: "POST", headers: J, body: JSON.stringify({ new_password }) });

/** Xoá tài khoản. */
export const deleteUser = (username: string) =>
  req<{ detail: string }>(`/api/users/${encodeURIComponent(username)}`, { method: "DELETE" });
