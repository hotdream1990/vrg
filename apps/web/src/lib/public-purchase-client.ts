/* Client link CÔNG KHAI nhập giá mủ nước — dùng fetch trần (KHÔNG gắn JWT nội bộ). */

import { API } from "./http";

/** `closed`: câu báo khi hôm nay đã quá hạn nhập (qua giờ chốt) — null = còn nhập được. */
export type PublicAuthResult = { token: string; units: string[]; today: string; closed?: string | null };
export type RecentRow = { as_of: string; price: number };

const J = { "Content-Type": "application/json" };

/** Lỗi HTTP kèm mã — trang cần tách 403 (bị chặn: quá giờ chốt / đã chốt số liệu) khỏi lỗi khác. */
export class PublicHttpError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

async function post<T>(path: string, body: unknown, token?: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      method: "POST",
      headers: token ? { ...J, Authorization: `Bearer ${token}` } : J,
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Không kết nối được máy chủ — kiểm tra mạng.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new PublicHttpError((data as { detail?: string })?.detail || `Lỗi (${res.status})`, res.status);
  return data as T;
}

export const publicAuth = (password: string) =>
  post<PublicAuthResult>("/api/public/purchase/auth", { password });

export const publicSubmit = (token: string, company: string, price: number) =>
  post<{ ok: boolean; as_of: string }>("/api/public/purchase", { company, price }, token);

export const publicRecent = (token: string, company: string) =>
  post<{ records: RecentRow[] }>("/api/public/purchase/recent", { company }, token);
