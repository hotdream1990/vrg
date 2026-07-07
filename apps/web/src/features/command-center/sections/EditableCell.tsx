import { useRef, useState } from "react";

const fmt = (v: number | null | undefined, d: number) =>
  v == null ? "" : v.toLocaleString("vi-VN", { maximumFractionDigits: d });

/** Ô số tự quản lý trạng thái sửa: bấm → input, Enter/blur (rời ô) lưu, Esc huỷ. */
export default function EditableCell({
  value, dec = 0, onSave, readOnly = false,
}: { value: number | null | undefined; dec?: number; onSave: (n: number) => void; readOnly?: boolean }) {
  const [editing, setEditing] = useState(false);
  const [v, setV] = useState("");
  const cancelled = useRef(false); // Esc đặt cờ này để onBlur không lưu

  if (readOnly) {
    return value != null ? <>{fmt(value, dec)}</> : <span style={{ color: "var(--muted)" }}>—</span>;
  }

  // Lưu khi rời ô (Enter/click ra ngoài đều đi qua đây); bỏ qua nếu Esc hoặc giá trị không đổi.
  const commit = () => {
    setEditing(false);
    if (cancelled.current) { cancelled.current = false; return; }
    const n = Number(v.replace(/[.,\s]/g, ""));
    if (v.trim() && !isNaN(n) && n !== value) onSave(n);
  };

  if (editing) {
    return (
      <input
        autoFocus className="blt-cell-input" value={v}
        style={{ width: 72, padding: "2px 4px", fontSize: 12 }}
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();               // → lưu qua onBlur
          else if (e.key === "Escape") { cancelled.current = true; e.currentTarget.blur(); }
        }}
        onBlur={commit}
      />
    );
  }
  return (
    <span style={{ cursor: "pointer", display: "block", minWidth: 56 }}
      onClick={() => { setEditing(true); setV(value != null ? String(value) : ""); }}>
      {value != null ? fmt(value, dec) : <span style={{ color: "var(--muted)" }}>—</span>}
    </span>
  );
}
