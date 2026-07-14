import { Button, Result } from "antd";
import { Link, Outlet } from "react-router-dom";

import type { Cap } from "../../lib/permissions";
import { useAuth } from "./AuthContext";

/* Chặn route theo QUYỀN MỤC DỮ LIỆU — cho qua nếu tài khoản có ÍT NHẤT MỘT quyền trong `caps`
   (admin=tất cả, viewer=không). Chặn gõ thẳng URL. Đặt BÊN TRONG ProtectedRoute. */
export default function RequireCap({ caps }: { caps: Cap[] }) {
  const { can } = useAuth();

  if (caps.some((c) => can(c))) return <Outlet />;
  return (
    <Result
      status="403"
      title="403 — Không đủ quyền"
      subTitle="Tài khoản của bạn chưa được cấp quyền truy cập mục này. Vui lòng liên hệ quản trị viên."
      extra={
        <Link to="/">
          <Button type="primary">Về trang chủ</Button>
        </Link>
      }
    />
  );
}
