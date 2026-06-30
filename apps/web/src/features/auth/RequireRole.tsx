import { Button, Result } from "antd";
import { Link, Outlet } from "react-router-dom";

import { useAuth } from "./AuthContext";

/* Chặn route theo vai trò (RBAC). Dùng bọc các route admin để viewer/editor gõ thẳng URL
   không vào được — thay vì để trang render rồi API trả 403. Đặt BÊN TRONG ProtectedRoute. */
export default function RequireRole({ roles }: { roles: string[] }) {
  const { user } = useAuth();

  if (user && roles.includes(user.role)) return <Outlet />;
  return (
    <Result
      status="403"
      title="403 — Không đủ quyền"
      subTitle="Tài khoản của bạn không có quyền truy cập trang này. Vui lòng liên hệ quản trị viên."
      extra={
        <Link to="/">
          <Button type="primary">Về trang chủ</Button>
        </Link>
      }
    />
  );
}
