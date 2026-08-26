/* Client API Đơn vị thành viên (member_unit). */

import { apiFetch } from "./http";

export type MemberUnit = {
  name: string; sort_order: number; is_active: boolean; region: string | null;
  country: string; currency: string;   // VN/VND mặc định; ≠VND ⇒ đơn vị nước ngoài cần tỷ giá
  has_factory: boolean;                 // có nhà máy chế biến; false ⇒ nhập tồn kho nguyên liệu
  parent_company: string | null;        // công ty mẹ đã gán (cây mẹ-con, chỉ dùng cho báo cáo cấp Tập đoàn)
  // SÁP NHẬP: đơn vị này đã nhập vào đơn vị nào, từ ngày nào. Số liệu TRƯỚC ngày đó vẫn đứng tên
  // đơn vị này — báo cáo mặc định gộp về đơn vị mới, có công tắc tách ra xem riêng.
  merged_into: string | null;
  merged_at: string | null;             // 'YYYY-MM-DD'
};

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

/** Gán đơn vị vào 1 khu vực (region=null để bỏ gán). */
export const setUnitRegion = (name: string, region: string | null) =>
  req<MemberUnit[]>(`/api/member-units/${encodeURIComponent(name)}`,
    { method: "PUT", headers: J, body: JSON.stringify({ set_region: true, region }) });

/** Gán quốc gia + loại tiền cho đơn vị (đơn vị nước ngoài dùng để bật ô tỷ giá khi thu mua). */
export const setUnitLocale = (name: string, country: string, currency: string) =>
  req<MemberUnit[]>(`/api/member-units/${encodeURIComponent(name)}`,
    { method: "PUT", headers: J, body: JSON.stringify({ set_locale: true, country, currency }) });

/** Đặt cờ đơn vị có nhà máy chế biến (không nhà máy ⇒ nhập tồn kho nguyên liệu ở biểu Tiêu thụ). */
export const setUnitFactory = (name: string, hasFactory: boolean) =>
  req<MemberUnit[]>(`/api/member-units/${encodeURIComponent(name)}`,
    { method: "PUT", headers: J, body: JSON.stringify({ set_factory: true, has_factory: hasFactory }) });

/** Gán công ty mẹ cho đơn vị (parent=null để bỏ gán) — cây công ty mẹ-con. */
export const setUnitParent = (name: string, parent: string | null) =>
  req<MemberUnit[]>(`/api/member-units/${encodeURIComponent(name)}`,
    { method: "PUT", headers: J, body: JSON.stringify({ set_parent: true, parent_company: parent }) });

/** Sáp nhập đơn vị `name` vào `into` kể từ ngày `at` — KHÔNG chuyển số liệu cũ sang đơn vị mới. */
export const mergeUnit = (name: string, into: string, at: string) =>
  req<{ units: MemberUnit[] }>(`/api/member-units/${encodeURIComponent(name)}/merge`,
    { method: "POST", headers: J, body: JSON.stringify({ merged_into: into, merged_at: at }) })
    .then((r) => r.units);

/** Gỡ sáp nhập — đơn vị hoạt động độc lập trở lại (tài khoản KHÔNG tự trả về, cấp lại tay). */
export const unmergeUnit = (name: string) =>
  req<{ units: MemberUnit[] }>(`/api/member-units/${encodeURIComponent(name)}/merge`,
    { method: "DELETE" }).then((r) => r.units);

/** Sắp xếp lại theo thứ tự danh sách tên. */
export const reorderUnits = (names: string[]) =>
  req<MemberUnit[]>(`/api/member-units/reorder`, { method: "POST", headers: J, body: JSON.stringify({ names }) });

/** Xoá đơn vị khỏi danh sách. */
export const deleteUnit = (name: string) =>
  req<MemberUnit[]>(`/api/member-units/${encodeURIComponent(name)}`, { method: "DELETE" });
