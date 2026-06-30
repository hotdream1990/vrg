/* Client API Đơn vị thành viên (member_unit). */

import { apiFetch } from "./http";

export type MemberUnit = { name: string; sort_order: number; is_active: boolean };

const req = apiFetch;

const J = { "Content-Type": "application/json" };

/** Danh sách đơn vị thành viên (theo thứ tự). */
export const listUnits = (includeInactive = true) =>
  req<MemberUnit[]>(`/api/member-units?include_inactive=${includeInactive}`);

/** Thêm đơn vị mới. */
export const addUnit = (name: string) =>
  req<MemberUnit[]>(`/api/member-units`, { method: "POST", headers: J, body: JSON.stringify({ name }) });

/** Đổi tên (migrate giá) và/hoặc bật-tắt active. */
export const updateUnit = (name: string, body: { new_name?: string; is_active?: boolean }) =>
  req<MemberUnit[]>(`/api/member-units/${encodeURIComponent(name)}`,
    { method: "PUT", headers: J, body: JSON.stringify(body) });

/** Sắp xếp lại theo thứ tự danh sách tên. */
export const reorderUnits = (names: string[]) =>
  req<MemberUnit[]>(`/api/member-units/reorder`, { method: "POST", headers: J, body: JSON.stringify({ names }) });

/** Xoá đơn vị khỏi danh sách. */
export const deleteUnit = (name: string) =>
  req<MemberUnit[]>(`/api/member-units/${encodeURIComponent(name)}`, { method: "DELETE" });
