import { EyeOutlined } from "@ant-design/icons";
import { Alert } from "antd";

import { useAuth } from "../../auth/AuthContext";

/** Banner báo chế độ chỉ xem cho viewer (ẩn nếu user được phép nhập/sửa). */
export default function ReadOnlyNotice() {
  const { canEdit } = useAuth();
  if (canEdit) return null;
  return (
    <Alert
      type="info" showIcon icon={<EyeOutlined />}
      style={{ marginBottom: 14 }}
      message="Chế độ chỉ xem — tài khoản của bạn không có quyền nhập/sửa số liệu."
    />
  );
}
