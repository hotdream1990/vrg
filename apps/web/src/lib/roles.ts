/* Vai trò RBAC — nhãn + màu dùng chung (trang Người dùng + bảng phân quyền). Khớp backend
   security.py: admin=require_admin · editor=require_editor · viewer=chỉ get_current_user.
   Hai vai trò GẮN ĐƠN VỊ (UNIT_ROLES ở backend): `member` nhập số liệu của đơn vị theo LOẠI NHẬP LIỆU
   được giao (Thu mua · Tồn kho · Hợp đồng & tiêu thụ — lib/entry-types.ts), `leader` (lãnh đạo đơn vị)
   xem số liệu đơn vị mình (chỉ xem). Cả hai dùng hộp thư Hỗ trợ & Thông báo: từ 01/10/2026 chuyên
   viên đơn vị cũng nhận thông báo (theo nhóm người nhận Tập đoàn chọn) và tự mở yêu cầu hỗ trợ.
   `executive` (Lãnh đạo Tập đoàn): xem mọi báo cáo · thống kê · AI mức Tập đoàn, không sửa gì,
   không có phần kỹ thuật/quản trị (backend: EXECUTIVE_CAPS + executive_readonly_guard.py). */

export type Role = { value: string; label: string; color: string };

export const ROLES: Role[] = [
  { value: "admin", label: "Quản trị viên", color: "green" },
  { value: "executive", label: "Lãnh đạo Tập đoàn", color: "volcano" },
  { value: "editor", label: "Chuyên viên nhập liệu", color: "blue" },
  { value: "viewer", label: "Người xem", color: "default" },
  { value: "member", label: "Đơn vị thành viên", color: "gold" },
  { value: "leader", label: "Lãnh đạo đơn vị thành viên", color: "purple" },
];

export const ROLE_LABEL: Record<string, string> = Object.fromEntries(ROLES.map((r) => [r.value, r.label]));
export const ROLE_COLOR: Record<string, string> = Object.fromEntries(ROLES.map((r) => [r.value, r.color]));

/** Vai trò BẮT BUỘC gán đơn vị thành viên (khớp `UNIT_ROLES` ở backend). */
export const UNIT_ROLES = new Set(["member", "leader"]);
