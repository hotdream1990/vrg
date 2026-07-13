/* Ô nhập số có định dạng nghìn (vi-VN) — dùng chung cho các form giá.
   `prevValue` (tuỳ chọn) = giá kỳ trước; lệch ≥10% → viền vàng + icon cảnh báo. */

import { isBigChange } from "../../../lib/change-warning";
import ChangeWarn from "./ChangeWarn";

type Props = {
  value: number | null;
  onChange: (v: number | null) => void;
  readOnly?: boolean;
  placeholder?: string;
  className?: string;
  prevValue?: number | null;
};

const fmt = (v: number | null) => (v != null ? v.toLocaleString("vi-VN") : "");
const parse = (s: string): number | null => {
  const n = Number(s.replace(/[.,\s]/g, ""));
  return s.trim() && !isNaN(n) ? n : null;
};

export default function NumInput({ value, onChange, readOnly, placeholder = "—", className, prevValue }: Props) {
  const warn = isBigChange(value, prevValue);
  const input = (
    <input
      type="text"
      inputMode="numeric"
      className={`${className ?? "blt-cell-input"}${warn ? " num-warn" : ""}`}
      value={fmt(value)}
      readOnly={readOnly}
      placeholder={placeholder}
      onChange={(e) => onChange(parse(e.target.value))}
    />
  );
  if (!warn) return input;
  return <span className="num-warn-wrap">{input}<ChangeWarn value={value} prev={prevValue} /></span>;
}
