/* Client API đăng nhập + hồ sơ cá nhân. */

import { API } from "./api-client";
import { authHeaders, onUnauthorized } from "./auth-token";

export type User = { username: string; full_name: string | null; role: string };
export type LoginResult = { access_token: string; token_type: string; user: User };

/** Đăng nhập → trả token + user. Ném lỗi (message tiếng Việt) nếu sai. */
export async function login(username: string, password: string): Promise<LoginResult> {
  let res: Response;
  try {
    res = await fetch(`${API}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  } catch {
    throw new Error("Không kết nối được máy chủ (" + API + ")");
  }
  if (!res.ok) {
    let msg = "Đăng nhập thất bại";
    try { const b = await res.json(); msg = b.detail || msg; } catch { /* ignore */ }
    throw new Error(msg);
  }
  return (await res.json()) as LoginResult;
}

/** Lấy thông tin user của token hiện tại (null nếu token sai/hết hạn). */
export async function fetchMe(): Promise<User | null> {
  try {
    const res = await fetch(`${API}/api/auth/me`, { headers: authHeaders() });
    if (!res.ok) return null;
    return (await res.json()) as User;
  } catch {
    return null;
  }
}

async function authReq<T>(path: string, init: RequestInit): Promise<T> {
  let res: Response;
  try { res = await fetch(`${API}${path}`, { ...init, headers: { "Content-Type": "application/json", ...authHeaders(), ...(init.headers ?? {}) } }); }
  catch { throw new Error("Không kết nối được API (" + API + ")"); }
  if (res.status === 401) { onUnauthorized(); throw new Error("Phiên đăng nhập đã hết hạn"); }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const b = await res.json(); msg = b.detail || msg; } catch { /* ignore */ }
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

/** User tự cập nhật hồ sơ (họ tên). */
export const updateProfile = (full_name: string | null) =>
  authReq<User>(`/api/auth/me`, { method: "PUT", body: JSON.stringify({ full_name }) });

/** User tự đổi mật khẩu. */
export const changePassword = (old_password: string, new_password: string) =>
  authReq<{ detail: string }>(`/api/auth/change-password`,
    { method: "POST", body: JSON.stringify({ old_password, new_password }) });
