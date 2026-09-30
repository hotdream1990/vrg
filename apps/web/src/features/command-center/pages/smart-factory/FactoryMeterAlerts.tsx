/* Các thông báo trạng thái của màn Chỉ số điện · nước · số bành: chưa có nhà máy · nhà máy chưa khai
   tag · lỗi đọc SCADA (429 = đang có lượt đọc khác → cảnh báo vàng, còn lại → lỗi đỏ). */

import { ReloadOutlined, SettingOutlined } from "@ant-design/icons";
import { Alert, Button } from "antd";
import { Link } from "react-router-dom";

export const SCADA_CONFIG_PATH = "/quan-tri/cau-hinh?tab=scada";

/** Lỗi tải chỉ số: giữ mã HTTP để chọn kiểu thông báo. */
export type MeterLoadError = { text: string; status: number };

const ConfigButton = () => (
  <Link to={SCADA_CONFIG_PATH}>
    <Button type="primary" icon={<SettingOutlined />}>Cấu hình kết nối</Button>
  </Link>
);

export function NoFactory({ isAdmin }: { isAdmin: boolean }) {
  return (
    <Alert
      type="info" showIcon className="sf-alert"
      title="Chưa có nhà máy nào được cấu hình kết nối SCADA"
      description={isAdmin
        ? "Khai máy chủ SQL Server và tag điện · nước · số bành của nhà máy ở trang Cấu hình kết nối SCADA."
        : "Liên hệ quản trị viên để khai kết nối SCADA cho nhà máy."}
      action={isAdmin && <ConfigButton />}
    />
  );
}

/** Nhà máy chưa khai tag nào → không gọi SCADA (server cũng trả 400). */
export function NoTags({ name, isAdmin }: { name: string; isAdmin: boolean }) {
  return (
    <Alert
      type="info" showIcon className="sf-alert"
      title="Nhà máy chưa khai tag nào"
      description={isAdmin
        ? `Khai tag điện · nước · số bành của ${name} ở trang Cấu hình kết nối SCADA.`
        : `Liên hệ quản trị viên để khai tag điện · nước · số bành cho ${name}.`}
      action={isAdmin && <ConfigButton />}
    />
  );
}

export function LoadErrorAlert({ error, onRetry }: { error: MeterLoadError; onRetry: () => void }) {
  const busy = error.status === 429;
  return (
    <Alert
      type={busy ? "warning" : "error"} showIcon className="sf-alert"
      title={busy ? "SCADA của nhà máy đang bận đọc số liệu" : "Không đọc được số liệu SCADA"}
      description={error.text}
      action={<Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>Thử lại</Button>}
    />
  );
}
