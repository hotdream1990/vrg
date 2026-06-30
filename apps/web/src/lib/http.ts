/* Lõi gọi API dùng chung cho mọi client.
   Tập trung xử lý: gắn Bearer token · 401 (hết phiên → về /login) · 403 (không đủ quyền)
   · lỗi kết nối · đọc message lỗi (`detail`) từ FastAPI. Sửa 1 chỗ, mọi client hưởng. */

import { authHeaders, onUnauthorized } from "./auth-token";

export const API = import.meta.env.VITE_API_URL ?? "http://localhost:8390";

/** Lấy `detail` (message tiếng Việt từ FastAPI) trong body lỗi; fallback `HTTP <status>`. */
async function errorMessage(res: Response, fallback?: string): Promise<string> {
  const base = fallback ?? `HTTP ${res.status}`;
  try {
    const body = await res.json();
    if (body && typeof body.detail === "string") return body.detail;
  } catch {
    /* body không phải JSON — dùng fallback */
  }
  return base;
}

/** Gọi API + parse JSON. Ném Error với message thân thiện cho mọi nhánh lỗi. */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      ...init,
      headers: { ...authHeaders(), ...(init?.headers ?? {}) },
    });
  } catch {
    throw new Error(`Không kết nối được máy chủ (${API}) — kiểm tra mạng hoặc thử lại.`);
  }
  if (res.status === 401) {
    onUnauthorized();
    throw new Error("Phiên đăng nhập đã hết hạn — vui lòng đăng nhập lại.");
  }
  if (res.status === 403) {
    throw new Error(await errorMessage(res, "Bạn không có quyền thực hiện thao tác này."));
  }
  if (!res.ok) {
    throw new Error(await errorMessage(res));
  }
  return (await res.json()) as T;
}
