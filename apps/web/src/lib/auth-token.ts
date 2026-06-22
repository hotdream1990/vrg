/* Token JWT lưu localStorage + header Authorization dùng chung cho mọi client API. */

const KEY = "vrg_token";

export const getToken = (): string | null => localStorage.getItem(KEY);
export const setToken = (t: string): void => localStorage.setItem(KEY, t);
export const clearToken = (): void => localStorage.removeItem(KEY);

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
