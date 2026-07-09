/* Client API Khu vực (member_region) — nhóm đơn vị thành viên. */

import { apiFetch } from "./http";

export type MemberRegion = { name: string; sort_order: number; is_active: boolean };

const req = apiFetch;
const J = { "Content-Type": "application/json" };

/** Danh sách khu vực (theo thứ tự). */
export const listRegions = (includeInactive = true) =>
  req<MemberRegion[]>(`/api/member-regions?include_inactive=${includeInactive}`);

/** Thêm khu vực mới. */
export const addRegion = (name: string) =>
  req<MemberRegion[]>(`/api/member-regions`, { method: "POST", headers: J, body: JSON.stringify({ name }) });

/** Đổi tên (giữ liên kết đơn vị) và/hoặc bật-tắt active. */
export const updateRegion = (name: string, body: { new_name?: string; is_active?: boolean }) =>
  req<MemberRegion[]>(`/api/member-regions/${encodeURIComponent(name)}`,
    { method: "PUT", headers: J, body: JSON.stringify(body) });

/** Sắp xếp lại theo thứ tự danh sách tên. */
export const reorderRegions = (names: string[]) =>
  req<MemberRegion[]>(`/api/member-regions/reorder`, { method: "POST", headers: J, body: JSON.stringify({ names }) });

/** Xoá khu vực (gỡ liên kết các đơn vị thuộc khu vực này). */
export const deleteRegion = (name: string) =>
  req<MemberRegion[]>(`/api/member-regions/${encodeURIComponent(name)}`, { method: "DELETE" });
