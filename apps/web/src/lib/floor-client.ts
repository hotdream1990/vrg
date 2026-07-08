/* Client API Giá sàn Tập đoàn (biểu giá theo lần). */

import { apiFetch } from "./http";

export type FloorItem = { grade: string; fob_usd: number | null; domestic_vnd: number | null };
export type FloorSchedule = { lan: number; as_of: string; title: string; items: FloorItem[] };
export type FloorSummary = {
  lan: number; as_of: string; title: string; grades: number; filled: number; updated: string | null;
};

const req = apiFetch;

/** Danh sách biểu giá (mỗi lần 1 dòng), lọc theo ngày áp dụng. */
export const listFloors = (dateFrom?: string, dateTo?: string) => {
  const p = new URLSearchParams();
  if (dateFrom) p.set("date_from", dateFrom);
  if (dateTo) p.set("date_to", dateTo);
  return req<FloorSummary[]>(`/api/floor?${p}`);
};

/** 1 biểu giá đầy đủ theo lần. */
export const getFloor = (lan: number) => req<FloorSchedule>(`/api/floor/${lan}`);

/** Số lần kế tiếp + danh sách chủng loại mặc định (dựng form tạo mới). */
export const nextFloorMeta = () => req<{ next_lan: number; grades: string[] }>(`/api/floor/next-lan`);

/** Tạo biểu giá mới — số lần tự nhảy ở backend; title = tiêu đề custom. */
export const createFloor = (as_of: string, items: FloorItem[], title?: string) =>
  req<FloorSchedule>(`/api/floor`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ as_of, title, items }),
  });

/** Sửa biểu giá lần đã có. */
export const updateFloor = (lan: number, as_of: string, items: FloorItem[], title?: string) =>
  req<FloorSchedule>(`/api/floor/${lan}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ as_of, title, items }),
  });

/** Xoá 1 biểu giá theo lần. */
export const deleteFloor = (lan: number) =>
  req<{ deleted: number }>(`/api/floor/${lan}`, { method: "DELETE" });
