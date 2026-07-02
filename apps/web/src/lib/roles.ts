/* 3 vai trò RBAC — nhãn + màu dùng chung (trang Người dùng + bảng phân quyền). Khớp backend
   security.py: admin=require_admin · editor=require_editor · viewer=chỉ get_current_user. */

export type Role = { value: string; label: string; color: string };

export const ROLES: Role[] = [
  { value: "admin", label: "Quản trị viên", color: "green" },
  { value: "editor", label: "Chuyên viên nhập liệu", color: "blue" },
  { value: "viewer", label: "Người xem", color: "default" },
];

export const ROLE_LABEL: Record<string, string> = Object.fromEntries(ROLES.map((r) => [r.value, r.label]));
export const ROLE_COLOR: Record<string, string> = Object.fromEntries(ROLES.map((r) => [r.value, r.color]));
