/* Client API cho tài khoản ĐƠN VỊ THÀNH VIÊN — tự xem/nhập giá mủ nước + mủ chén của CÁC đơn vị được gán.
   Backend scope theo token (get_current_member): mỗi thao tác ghi kèm `company` và server kiểm tra
   company thuộc danh sách gán của tài khoản. */

import { apiFetch } from "./http";

export type MemberPriceType = "purchase" | "purchase_cup";

export type UnitSheet = {
  purchase: Record<string, number>;      // {date: giá mủ nước (đồng/độ TSC)}
  purchase_cup: Record<string, number>;  // {date: giá mủ chén (đồng/độ TSC)}
  dates: string[];                       // ngày có dữ liệu (mới → cũ)
};

export type MemberPrices = {
  units: string[];                       // các đơn vị được gán
  today: string;                         // YYYY-MM-DD (giờ VN, để tính cửa sổ sửa)
  edit_window_days: number;              // sửa được: hôm nay + N ngày gần nhất
  sheets: Record<string, UnitSheet>;     // {đơn vị: lịch sử giá}
};

const J = { "Content-Type": "application/json" };

/** Lịch sử giá mủ nước + mủ chén của tất cả đơn vị được gán. */
export const fetchMyPrices = (days = 30) =>
  apiFetch<MemberPrices>(`/api/member/prices?days=${days}`);

/** Nhập/sửa 1 ô giá cho 1 đơn vị được gán, ngày trong cửa sổ cho phép. */
export const upsertMyPrice = (company: string, as_of: string, price_type: MemberPriceType, price: number) =>
  apiFetch<{ ok: boolean }>(`/api/member/prices`,
    { method: "PUT", headers: J, body: JSON.stringify({ company, as_of, price_type, price }) });

/** Xoá 1 ô giá của 1 đơn vị được gán. */
export const clearMyPrice = (company: string, as_of: string, price_type: MemberPriceType) =>
  apiFetch<{ deleted: boolean }>(
    `/api/member/prices?company=${encodeURIComponent(company)}&as_of=${as_of}&price_type=${price_type}`,
    { method: "DELETE" });
