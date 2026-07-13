/* Icon cảnh báo (vàng) khi giá trị mới lệch ≥10% so với kỳ trước — ẩn nếu không lệch/thiếu số. */

import { WarningOutlined } from "@ant-design/icons";
import { Tooltip } from "antd";

import { changeLabel, isBigChange } from "../../../lib/change-warning";

const vnum = (n: number) => n.toLocaleString("vi-VN");

export default function ChangeWarn(
  { value, prev, style }: { value: number | null | undefined; prev: number | null | undefined; style?: React.CSSProperties },
) {
  if (!isBigChange(value, prev)) return null;
  return (
    <Tooltip title={`Lệch ${changeLabel(value as number, prev as number)} so với kỳ trước (cũ: ${vnum(prev as number)}) — kiểm tra lại số liệu`}>
      <WarningOutlined style={{ color: "var(--warn)", cursor: "help", ...style }} />
    </Tooltip>
  );
}
