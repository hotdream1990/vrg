/* Ô nhập số có định dạng nghìn (vi-VN) — dùng chung cho các form giá. */

type Props = {
  value: number | null;
  onChange: (v: number | null) => void;
  readOnly?: boolean;
  placeholder?: string;
  className?: string;
};

const fmt = (v: number | null) => (v != null ? v.toLocaleString("vi-VN") : "");
const parse = (s: string): number | null => {
  const n = Number(s.replace(/[.,\s]/g, ""));
  return s.trim() && !isNaN(n) ? n : null;
};

export default function NumInput({ value, onChange, readOnly, placeholder = "—", className }: Props) {
  return (
    <input
      type="text"
      inputMode="numeric"
      className={className ?? "blt-cell-input"}
      value={fmt(value)}
      readOnly={readOnly}
      placeholder={placeholder}
      onChange={(e) => onChange(parse(e.target.value))}
    />
  );
}
