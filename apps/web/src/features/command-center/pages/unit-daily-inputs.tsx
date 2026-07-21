/* Ô nhập số + hộp chỉ đọc dùng chung cho form Thu mua & Tiêu thụ–Tồn kho.
   Định dạng số kiểu vi-VN: nhóm nghìn "." + thập phân ",". */

import { InputNumber } from "antd";

const groupInt = (s: string) => s.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
export const fmtInput = (v?: string | number): string => {
  if (v === "" || v == null) return "";
  const s = String(v);
  const neg = s.startsWith("-") ? "-" : "";
  const [intp, dec] = s.replace("-", "").split(".");
  return neg + groupInt(intp || "0") + (dec != null ? `,${dec}` : "");
};
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
    (mặc định của antd là 32px, lệch hẳn so với Select size="small" 24px). */
export const numInput = (
  value: number | null, onChange: (v: number | null) => void, readOnly?: boolean,
  size?: "small",
) => (
  <InputNumber
    value={value}
    onChange={(v) => onChange(v as number | null)}
    disabled={readOnly}
    size={size}
    controls={false}
    min={0}
    formatter={fmtInput}
    parser={parseInput}
    style={{ width: "100%" }}
    placeholder="—"
  />
);

/** Nhãn ô + đơn vị (dùng chung). */
export const fieldLabel = (label: React.ReactNode, unit?: string) => (
  <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 2 }}>
    {label}{unit ? <> <span style={{ opacity: 0.6 }}>({unit})</span></> : null}
  </div>
);
