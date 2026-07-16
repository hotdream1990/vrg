/* Cài đặt đọc-được cho mọi tài khoản đăng nhập (cửa sổ nhập liệu). */

import { apiFetch } from "./http";

export type EditWindows = {
  member_days: number; // số ngày sửa được — trang Giá thu mua (đơn vị thành viên)
  editor_days: number; // số ngày sửa được — chuyên viên nhập liệu
  today: string;       // hôm nay (YYYY-MM-DD, giờ VN) để tính cửa sổ
};

export const fetchEditWindows = () => apiFetch<EditWindows>("/api/settings/edit-windows");
