/* Cài đặt đọc-được cho mọi tài khoản đăng nhập (cửa sổ nhập liệu). */

import { apiFetch } from "./http";

export type EditWindows = {
  member_days: number;           // N — đơn vị thành viên (hạn = giờ chốt của ngày D + N)
  editor_days: number;           // N — chuyên viên nhập liệu
  member_editable_from: string;  // ngày cũ nhất đơn vị còn sửa được NGAY LÚC NÀY (server đã tính giờ chốt)
  editor_editable_from: string;  // như trên, cho chuyên viên
  cutoff_hour: number;           // giờ chốt 0–23 (giờ VN), mặc định 11
  today: string;                 // hôm nay (YYYY-MM-DD, giờ VN)
  now: string;                   // giờ server lúc trả lời (ISO, có múi giờ)
  next_change_at: string;        // giờ chốt kế tiếp (ISO, có múi giờ) — mốc cửa sổ trượt, web hẹn giờ tải lại
};

export const fetchEditWindows = () => apiFetch<EditWindows>("/api/settings/edit-windows");
