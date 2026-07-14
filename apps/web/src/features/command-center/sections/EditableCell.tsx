import { useRef, useState } from "react";

import { isBigChange } from "../../../lib/change-warning";
import ChangeWarn from "./ChangeWarn";

const fmt = (v: number | null | undefined, d: number) =>
  v == null ? "" : v.toLocaleString("vi-VN", { maximumFractionDigits: d });

/** Ô số tự quản lý trạng thái sửa: bấm → input, Enter/blur (rời ô) lưu, Esc huỷ.
 *  Xoá trắng ô (rồi rời ô) → gọi `onClear` để xoá giá trị (nếu ô đang có giá).
 *  `prevValue` (tuỳ chọn) = giá kỳ trước; lệch ≥10% → viền vàng + icon cảnh báo. */
export default function EditableCell({
  value, dec = 0, onSave, onClear, readOnly = false, prevValue,
}: {
  value: number | null | undefined; dec?: number; onSave: (n: number) => void;
  onClear?: () => void; readOnly?: boolean; prevValue?: number | null;
}) {
  const [editing, setEditing] = useState(false);
  const [v, setV] = useState("");
  const cancelled = useRef(false); // Esc đặt cờ này để onBlur không lưu
  const warn = isBigChange(value, prevValue);

  if (readOnly) {
    return value != null
      ? <span className={warn ? "num-warn num-warn-wrap" : undefined} style={warn ? WARN_BOX : undefined}>
          {fmt(value, dec)}{warn && <ChangeWarn value={value} prev={prevValue} />}
        </span>
      : <span style={{ color: "var(--muted)" }}>—</span>;
  }

  // Lưu khi rời ô (Enter/click ra ngoài đều đi qua đây); bỏ qua nếu Esc hoặc giá trị không đổi.
  const commit = () => {
    setEditing(false);
    if (cancelled.current) { cancelled.current = false; return; }
    const raw = v.trim();
    if (!raw) {                                  // xoá trắng ô
      if (value != null) onClear?.();            // đang có giá → xoá; vốn trống → không làm gì
      return;
    }
    const n = Number(raw.replace(/[.,\s]/g, ""));
    if (!isNaN(n) && n !== value) onSave(n);
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
    <span style={{ cursor: "pointer", display: "block", minWidth: 56, ...(warn ? WARN_BOX : {}) }}
      className={warn ? "num-warn" : undefined}
      onClick={() => { setEditing(true); setV(value != null ? String(value) : ""); }}>
      {value != null ? fmt(value, dec) : <span style={{ color: "var(--muted)" }}>—</span>}
      {warn && <ChangeWarn value={value} prev={prevValue} style={{ marginLeft: 4 }} />}
    </span>
  );
}

const WARN_BOX: React.CSSProperties = { borderRadius: 4, padding: "0 4px" };
