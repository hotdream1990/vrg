/* Token JWT lưu localStorage + header Authorization dùng chung cho mọi client API. */

const KEY = "vrg_token";
const ADMIN_KEY = "vrg_admin_token"; // token admin gốc, cất tạm khi đang đăng nhập hộ (impersonation)

export const getToken = (): string | null => localStorage.getItem(KEY);
export const setToken = (t: string): void => localStorage.setItem(KEY, t);
export const clearToken = (): void => localStorage.removeItem(KEY);

/** Token admin gốc trong lúc đang đăng nhập hộ tài khoản khác (null = không trong phiên mạo danh). */
export const getAdminToken = (): string | null => localStorage.getItem(ADMIN_KEY);
export const setAdminToken = (t: string): void => localStorage.setItem(ADMIN_KEY, t);
export const clearAdminToken = (): void => localStorage.removeItem(ADMIN_KEY);

/** Header Bearer (rỗng nếu chưa đăng nhập). */
export const authHeaders = (): Record<string, string> => {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
};

/** Hết phiên (401) → xoá token + đẩy về /login. */
export const onUnauthorized = (): void => {
  clearToken();
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
};
