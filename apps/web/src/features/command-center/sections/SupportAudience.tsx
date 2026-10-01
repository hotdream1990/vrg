/* Nhóm người nhận phía đơn vị của thẻ Hỗ trợ & Thông báo / lịch nhắc (chốt 01/10/2026):
   lãnh đạo đơn vị và/hoặc chuyên viên nhập liệu theo loại (Thu mua · Tồn kho · Hợp đồng & tiêu thụ). */

import { Checkbox, Tag } from "antd";

import { AUDIENCES, AUDIENCE_LABEL, type Audience } from "../../../lib/entry-types";
import { audienceOf } from "./support-format";

const AUDIENCE_OPTIONS = AUDIENCES.map((a) => ({ value: a, label: AUDIENCE_LABEL[a] }));

/** Thẻ nhỏ liệt kê người nhận — thiếu/rỗng hiện "Lãnh đạo đơn vị" (dữ liệu cũ). */
export function AudienceTags({ audience }: { audience?: Audience[] | null }) {
  return (
    <>
      {audienceOf(audience).map((a) => (
        <Tag key={a} color="cyan">{AUDIENCE_LABEL[a] ?? a}</Tag>
      ))}
    </>
  );
}

/** Ô chọn người nhận (chọn nhiều, bắt buộc ≥ 1 — form gọi kiểm tra trước khi gửi). */
export function AudiencePicker({ value, onChange, disabled }: {
  value: Audience[]; onChange: (v: Audience[]) => void; disabled?: boolean;
}) {
  return (
    <div>
      <div className="sp-label" style={{ marginBottom: 6 }}>Gửi tới</div>
      <Checkbox.Group options={AUDIENCE_OPTIONS} value={value} disabled={disabled}
        onChange={(v) => onChange(v as Audience[])} />
    </div>
  );
}
