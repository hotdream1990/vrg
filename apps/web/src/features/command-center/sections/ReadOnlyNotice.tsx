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
  const { user, canEdit, canEditCap, canEditUnitData } = useAuth();
  const mayEdit = canEditUnitData
    || (cap ? (Array.isArray(cap) ? cap : [cap]).some(canEditCap) : canEdit);
  if (mayEdit) return null;
  // Lãnh đạo đơn vị không "thiếu quyền" — vai trò này vốn chỉ để theo dõi, nên nói đúng như vậy
  // và chỉ luôn ai là người nhập, tránh lãnh đạo đi hỏi quản trị cấp thêm quyền.
  const message = user?.role === "leader"
    ? "Chế độ chỉ xem — tài khoản lãnh đạo đơn vị theo dõi số liệu; việc nhập/sửa do tài khoản nhập liệu của đơn vị thực hiện."
    : user?.role === "executive"
      ? "Chế độ chỉ xem — tài khoản Lãnh đạo Tập đoàn theo dõi số liệu; việc nhập/sửa do chuyên viên thực hiện."
      : "Chế độ chỉ xem — tài khoản của bạn không có quyền nhập/sửa số liệu.";
  return (
    <Alert
      type="info" showIcon icon={<EyeOutlined />}
      style={{ marginBottom: 14 }}
      message={message}
    />
  );
}
