/* Client API Tồn kho Tập đoàn (fact_inventory) — đọc chuỗi tuần + nhập/sửa/xoá. */

import { API } from "./api-client";
import { authHeaders, onUnauthorized } from "./auth-token";

export type InventoryWeek = {
  as_of: string;
  ton_kho: number | null;
  ton_kho_hd: number | null;
  note: string | null;
  source: string;
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...authHeaders(), ...(init?.headers ?? {}) },
    });
  } catch {
    throw new Error("Không kết nối được API (" + API + ")");
  }
  if (res.status === 401) { onUnauthorized(); throw new Error("Phiên đăng nhập đã hết hạn"); }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const b = await res.json(); msg = b.detail || msg; } catch { /* ignore */ }
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

export const fetchInventory = () => req<InventoryWeek[]>(`/api/inventory`);

export const upsertInventory = (w: {
  as_of: string; ton_kho: number | null; ton_kho_hd: number | null; note?: string | null;
}) => req<InventoryWeek>(`/api/inventory`, { method: "POST", body: JSON.stringify(w) });

export const deleteInventory = (as_of: string) =>
  req<{ deleted: string }>(`/api/inventory/${as_of}`, { method: "DELETE" });
