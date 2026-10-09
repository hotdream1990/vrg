/* Đầu cột đơn vị ở bảng Kế hoạch năm (phía đơn vị): kế hoạch đã chốt cùng đợt chốt số liệu → "Đã chốt"
   + nút «Đề nghị sửa». Bấm → cột mở để sửa số, rồi «Gửi đề nghị» (Ban duyệt mới ghi thật) hoặc «Huỷ». */

import { CloseOutlined, EditOutlined, LockOutlined, SendOutlined } from "@ant-design/icons";
import { Alert, Button, Space, Tag, Tooltip } from "antd";

type Props = {
  locked: boolean;
  lockedUntil: string | null;
  canRequest: boolean;          // tài khoản nhập liệu (lãnh đạo đơn vị chỉ xem)
  requesting: boolean;          // cột đang ở chế độ soạn đề nghị
  busy: boolean;
  onStart: () => void;
  onSend: () => void;
  onCancel: () => void;
};

const dmy = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "");

export default function YearPlanLockCell({ locked, lockedUntil, canRequest, requesting, busy, onStart, onSend, onCancel }: Props) {
  if (!locked) return null;
  if (requesting) {
    return (
      <Space size={4} wrap>
        <Button size="small" type="primary" icon={<SendOutlined />} loading={busy} onClick={onSend}>Gửi đề nghị</Button>
        <Button size="small" icon={<CloseOutlined />} disabled={busy} onClick={onCancel}>Huỷ</Button>
      </Space>
    );
  }
  return (
    <Space size={4} wrap>
      <Tooltip title={lockedUntil ? `Đơn vị đã xác nhận chốt số liệu đến hết ngày ${dmy(lockedUntil)}` : undefined}>
        <Tag icon={<LockOutlined />} color="blue" style={{ marginInlineEnd: 0 }}>Đã chốt</Tag>
      </Tooltip>
      {canRequest && <Button size="small" icon={<EditOutlined />} onClick={onStart}>Đề nghị sửa</Button>}
    </Space>
  );
}

/** Lời nhắc đầu màn khi có đơn vị đã chốt kế hoạch năm đang xem. */
export function YearPlanLockBanner({ year, lockedUntil }: { year: number; lockedUntil: string | null }) {
  return (
    <Alert type="info" showIcon style={{ marginBottom: 12 }}
      title={`Kế hoạch năm ${year} đã chốt cùng đợt chốt số liệu`
        + (lockedUntil ? ` (đến hết ngày ${dmy(lockedUntil)})` : "")}
      description={<>Cột <b>Đã chốt</b> chỉ xem. Muốn sửa: bấm <b>Đề nghị sửa</b> ở đầu cột, chỉnh số rồi <b>Gửi đề nghị</b> để Ban duyệt.</>} />
  );
}
