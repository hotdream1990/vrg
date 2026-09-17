/* Client API Nhu cầu thị trường THEO TRƯỜNG (17/09/2026, bản rút gọn) — mỗi phiếu = một nhu cầu của
   MỘT chủng loại; thời gian giao và kết quả là ô chữ tự do (api-contract §3–§4).
   - Tài khoản đơn vị: `/api/member/market-demand/items` (server ép company ∈ đơn vị được gán).
   - Chuyên viên có quyền `market_demand`: `/api/market-demand/items` (mọi đơn vị). */

import { apiFetch } from "./http";

export type DemandQtyUnit = "ton" | "container";
/** VND = TRIỆU đồng/tấn · USD = USD/tấn. */
export type DemandCurrency = "VND" | "USD";

/** Thân `PUT …/items` (`id` rỗng = thêm mới). Ngày dạng YYYY-MM-DD. */
export interface DemandItemInput {
  id: number | null;
  company: string;
  as_of: string;
  customer: string;
  grade: string;
  qty: number | null;
  qty_unit: DemandQtyUnit;
  price: number | null;
  currency: DemandCurrency;
  delivery_place: string;
  /** Chữ tự do: "đến 30/11/2026", "T9+10/2026"… */
  delivery_time: string;
  /** Chữ tự do, trống = chưa có kết quả — sửa được cả khi phiếu đã quá hạn. */
  result: string;
  note: string;
}

export interface DemandItem extends DemandItemInput {
  id: number;
  /** Dòng chuyển từ bản chữ tự do cũ. */
  legacy: boolean;
  created_at: string;
  created_by: string | null;
  updated_at: string;
  updated_by: string | null;
}

export interface DemandList {
  units: string[];
  /** Đơn vị CHỈ XEM trong `units` — đã sáp nhập vào đơn vị của tài khoản (chỉ phía đơn vị). */
  view_only_units?: string[];
  today: string;
  edit_window_days: number;
  grades: string[];
  items: DemandItem[];
}

export type DemandFilter = {
  date_from?: string;
  date_to?: string;
  /** Chỉ endpoint chuyên viên nhận; phía đơn vị lọc tại trình duyệt. */
  company?: string;
  grade?: string;
  q?: string;
};

const J = { "Content-Type": "application/json" };
const MEMBER_BASE = "/api/member/market-demand/items";
const STAFF_BASE = "/api/market-demand/items";

/** Bỏ ô lọc trống khỏi query string. */
function qs(params: Record<string, string | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}

const list = (base: string, f: DemandFilter) => apiFetch<DemandList>(`${base}${qs(f)}`);
const save = (base: string, body: DemandItemInput) =>
  apiFetch<{ item: DemandItem }>(base, { method: "PUT", headers: J, body: JSON.stringify(body) });
const remove = (base: string, id: number) =>
  apiFetch<{ ok: boolean }>(`${base}/${id}`, { method: "DELETE" });

// ── Tài khoản đơn vị (nhập liệu + lãnh đạo đơn vị chỉ GET) ──
export const fetchMyDemandItems = (f: DemandFilter = {}) => list(MEMBER_BASE, { ...f, company: undefined });
export const saveMyDemandItem = (body: DemandItemInput) => save(MEMBER_BASE, body);
export const deleteMyDemandItem = (id: number) => remove(MEMBER_BASE, id);

// ── Chuyên viên có quyền (mọi đơn vị) ──
export const fetchDemandItems = (f: DemandFilter = {}) => list(STAFF_BASE, f);
export const saveDemandItem = (body: DemandItemInput) => save(STAFF_BASE, body);
export const deleteDemandItem = (id: number) => remove(STAFF_BASE, id);

/** Bộ hàm theo loại tài khoản — màn dùng chung cho đơn vị lẫn chuyên viên. */
export const demandApi = (unitAccount: boolean) => (unitAccount
  ? { fetch: fetchMyDemandItems, save: saveMyDemandItem, remove: deleteMyDemandItem }
  : { fetch: fetchDemandItems, save: saveDemandItem, remove: deleteDemandItem });
