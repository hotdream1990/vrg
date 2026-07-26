/* Ô nhập số + hộp chỉ đọc dùng chung cho form Thu mua & Tiêu thụ–Tồn kho.
   Định dạng số kiểu vi-VN: nhóm nghìn "." + thập phân ",". */

import { InputNumber, Tooltip } from "antd";

import { type Bound, boundWarning } from "../../../lib/entry-bounds";
import { formatViNumber } from "../../../lib/number-format";

// Dùng chung 1 nguồn định dạng số vi-VN (giữ nguyên chữ ký để antd suy kiểu InputNumber<string>).
export const fmtInput = (v?: string | number): string => formatViNumber(v);
export const parseInput = (s?: string): string => (s ?? "").replace(/\./g, "").replace(",", ".");

/** Hộp ô chỉ đọc (cột suy ra / tự quy đổi) — nền mờ, viền nét đứt. */
export const readOnlyBox = (text: string, tag: string) => (
  <div style={{
    height: 32, lineHeight: "32px", padding: "0 11px", borderRadius: 6, textAlign: "right",
    background: "rgba(125,125,125,.12)", border: "1px dashed rgba(125,125,125,.35)", fontWeight: 600,
  }}>
    {text}
    <span style={{ fontSize: 10, opacity: 0.55, fontWeight: 400 }}> · {tag}</span>
  </div>
);

/** Ô nhập số (vi-VN). `size="small"` cho ô nằm TRONG BẢNG — để cao bằng Select/nút cùng dòng
    (mặc định của antd là 32px, lệch hẳn so với Select size="small" 24px).
    `bound` (tuỳ chọn): số ra ngoài khoảng thường gặp → viền cam (status="warning") + tooltip nói rõ
    đơn vị tính (xem `lib/entry-bounds.ts`). CHỈ CẢNH BÁO — không chặn gõ, không chặn lưu.
    `warn` (tuỳ chọn): lời cảnh báo ép sẵn, dùng cho lỗi mà bản thân con số không nói lên được —
    vd ô TRỐNG vẫn phải cảnh báo (dòng USD chưa nhập tỷ giá). Ưu tiên hơn `bound`.
    Cách bọc GIỮ NGUYÊN cây phần tử để lúc cảnh báo bật/tắt không remount input → không mất focus
    khi đang gõ; chỉ đổi màu viền, không lệch layout. */
export const numInput = (
  value: number | null, onChange: (v: number | null) => void, readOnly?: boolean,
  size?: "small", bound?: Bound | null, warnText?: string | null,
) => {
  const warn = warnText ?? boundWarning(value, bound);
  const el = (
    <InputNumber
      value={value}
      onChange={(v) => onChange(v as number | null)}
      disabled={readOnly}
      size={size}
      controls={false}
      min={0}
      status={warn ? "warning" : undefined}
      formatter={fmtInput}
      parser={parseInput}
      style={{ width: "100%" }}
      placeholder="—"
    />
  );
  if (bound == null && warnText === undefined) return el;
  return <Tooltip title={warn ?? ""}>{el}</Tooltip>;
};

/** Nhãn ô + đơn vị (dùng chung). */
export const fieldLabel = (label: React.ReactNode, unit?: string) => (
  <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 2 }}>
    {label}{unit ? <> <span style={{ opacity: 0.6 }}>({unit})</span></> : null}
  </div>
);
