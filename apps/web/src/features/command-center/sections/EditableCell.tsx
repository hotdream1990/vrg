import { useState } from "react";

const fmt = (v: number | null | undefined, d: number) =>
  v == null ? "" : v.toLocaleString("vi-VN", { maximumFractionDigits: d });

/** Ô số tự quản lý trạng thái sửa: bấm → input, Enter/blur lưu, Esc huỷ. */
export default function EditableCell({
  value, dec = 0, onSave, readOnly = false,
}: { value: number | null | undefined; dec?: number; onSave: (n: number) => void; readOnly?: boolean }) {
  const [editing, setEditing] = useState(false);
  const [v, setV] = useState("");

  if (readOnly) {
    return value != null ? <>{fmt(value, dec)}</> : <span style={{ color: "var(--muted)" }}>—</span>;
  }

  if (editing) {
    return (
      <input
        autoFocus className="blt-cell-input" value={v}
        style={{ width: 72, padding: "2px 4px", fontSize: 12 }}
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            const n = Number(v.replace(/[.,\s]/g, ""));
            if (v.trim() && !isNaN(n)) onSave(n);
            setEditing(false);
          }
          if (e.key === "Escape") setEditing(false);
        }}
        onBlur={() => setEditing(false)}
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
