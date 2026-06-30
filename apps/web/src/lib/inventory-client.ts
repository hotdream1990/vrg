/* Client API Tồn kho Tập đoàn (fact_inventory) — đọc chuỗi tuần + nhập/sửa/xoá. */

import { apiFetch } from "./http";

export type InventoryWeek = {
  as_of: string;
  ton_kho: number | null;
  ton_kho_hd: number | null;
  note: string | null;
  source: string;
};

const req = <T>(path: string, init?: RequestInit): Promise<T> =>
  apiFetch<T>(path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });

export const fetchInventory = () => req<InventoryWeek[]>(`/api/inventory`);

export const upsertInventory = (w: {
  as_of: string; ton_kho: number | null; ton_kho_hd: number | null; note?: string | null;
}) => req<InventoryWeek>(`/api/inventory`, { method: "POST", body: JSON.stringify(w) });

export const deleteInventory = (as_of: string) =>
  req<{ deleted: string }>(`/api/inventory/${as_of}`, { method: "DELETE" });
