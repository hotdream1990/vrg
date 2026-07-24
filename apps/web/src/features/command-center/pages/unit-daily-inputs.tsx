/* Ô nhập số + hộp chỉ đọc dùng chung cho form Thu mua & Tiêu thụ–Tồn kho.
   Định dạng số kiểu vi-VN: nhóm nghìn "." + thập phân ",". */

import { InputNumber, Tooltip } from "antd";

import { formatViNumber } from "../../../lib/number-format";

/** Ngưỡng cảnh báo cho ô nhập theo TẤN: >1.000 tấn/ngày cho 1 đơn vị là bất thường (dễ nhầm kg
    hoặc dư số 0) → viền cam + tooltip nhắc kiểm tra (chỉ cảnh báo, không chặn lưu). */
export const TON_WARN_ABOVE = 1000;

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
    `warnAbove` (tuỳ chọn): giá trị > ngưỡng → viền cam (status="warning") + tooltip. Chỉ cột TẤN mới
    truyền (xem `TON_WARN_ABOVE`). Cách bọc GIỮ NGUYÊN cây phần tử (warnAbove là hằng theo ô) để đổi
    trạng thái không remount input → không mất focus khi đang gõ vượt ngưỡng; chỉ đổi màu viền, không lệch layout. */
export const numInput = (
  value: number | null, onChange: (v: number | null) => void, readOnly?: boolean,
  size?: "small", warnAbove?: number | null,
) => {
  const over = warnAbove != null && value != null && value > warnAbove;
  const el = (
    <InputNumber
      value={value}
      onChange={(v) => onChange(v as number | null)}
      disabled={readOnly}
      size={size}
      controls={false}
      min={0}
      status={over ? "warning" : undefined}
      formatter={fmtInput}
      parser={parseInput}
      style={{ width: "100%" }}
      placeholder="—"
    />
  );
  if (warnAbove == null) return el;
  return (
    <Tooltip title={over ? `Sản lượng vượt ${formatViNumber(warnAbove)} tấn — kiểm tra lại (đơn vị tính là TẤN, không phải kg)` : ""}>
      {el}
    </Tooltip>
  );
};

/** Nhãn ô + đơn vị (dùng chung). */
export const fieldLabel = (label: React.ReactNode, unit?: string) => (
  <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 2 }}>
    {label}{unit ? <> <span style={{ opacity: 0.6 }}>({unit})</span></> : null}
  </div>
);
