import { EyeOutlined } from "@ant-design/icons";
import { Alert } from "antd";

import type { Cap } from "../../../lib/permissions";
import { useAuth } from "../../auth/AuthContext";

/** Banner báo chế độ chỉ xem (ẩn nếu user được phép nhập/sửa).
 *
 * Truyền `cap` để bám đúng quyền của màn hình — tài khoản được cấp mục này ở mức Xem
 * cũng thấy banner. Nhiều cap = ghi được nếu ÍT NHẤT MỘT cap đạt mức Sửa (vd Báo giá).
 * Không truyền `cap` → chỉ xét vai trò (viewer). */
export default function ReadOnlyNotice({ cap }: { cap?: Cap | Cap[] } = {}) {
  const { canEdit, canEditCap } = useAuth();
  const mayEdit = cap ? (Array.isArray(cap) ? cap : [cap]).some(canEditCap) : canEdit;
  if (mayEdit) return null;
  return (
    <Alert
      type="info" showIcon icon={<EyeOutlined />}
      style={{ marginBottom: 14 }}
      message="Chế độ chỉ xem — tài khoản của bạn không có quyền nhập/sửa số liệu."
    />
  );
}
