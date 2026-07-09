import { ArrowDownOutlined, ArrowUpOutlined, MinusOutlined } from "@ant-design/icons";

import type { FloorAction, FloorConfidence, SuggestItem } from "../../../../lib/floor-suggest-client";
import { ACTION_LABEL, CONF_LABEL } from "../../../../lib/floor-rationale";

const fmt = (n: number | null) => (n == null ? "—" : n.toLocaleString("vi-VN"));
const sInt = (n: number | null) => (n == null ? "—" : (n > 0 ? "+" : "") + n.toLocaleString("vi-VN"));
const ACTION_COLOR: Record<FloorAction, string> = { raise: "#16a34a", hold: "#64748b", lower: "#e11d48" };
const CONF_COLOR: Record<FloorConfidence, string> = { high: "#16a34a", medium: "#ca8a04", low: "#94a3b8" };

function ActionTag({ action }: { action: FloorAction | null }) {
  if (!action) return <span style={{ color: "var(--muted)" }}>—</span>;
  const Icon = action === "raise" ? ArrowUpOutlined : action === "lower" ? ArrowDownOutlined : MinusOutlined;
  return (
    <span style={{ color: ACTION_COLOR[action], fontWeight: 700, whiteSpace: "nowrap" }}>
      <Icon style={{ marginRight: 4 }} />{ACTION_LABEL[action]}
    </span>
  );
}

function ConfTag({ c }: { c: FloorConfidence | null }) {
  if (!c) return <span style={{ color: "var(--muted)" }}>—</span>;
  return (
    <span style={{ fontSize: 11, fontWeight: 700, color: "#fff", background: CONF_COLOR[c], borderRadius: 10, padding: "1px 9px" }}>
      {CONF_LABEL[c]}
    </span>
  );
}

/** Bảng đề xuất điều chỉnh giá sàn so với lần trước. Bấm 1 dòng để chọn grade diễn giải. */
export default function AdjustmentTable(
  { items, focus, onFocus }: { items: SuggestItem[]; focus: string; onFocus: (g: string) => void },
) {
  return (
    <div className="card" style={{ padding: 0, overflow: "auto" }}>
      <table style={{ fontSize: 13 }}>
        <thead><tr>
          <th>Chủng loại</th>
          <th className="r">Giá sàn lần trước</th>
          <th className="r">Gợi ý mô hình</th>
          <th className="r">Đề xuất điều chỉnh</th>
          <th>Hành động</th>
          <th className="r">Đã ban hành (lần này)</th>
          <th className="r">Độ tin cậy</th>
        </tr></thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.grade} onClick={() => onFocus(it.grade)}
              style={{ cursor: "pointer", background: it.grade === focus ? "var(--card-2, #eef6f0)" : undefined }}>
              <td style={{ fontWeight: 500 }}>
                {it.grade}
                {it.unit && it.unit !== "USD/T" && (
                  <span style={{ fontSize: 11, marginLeft: 6, color: "var(--muted)", fontWeight: 400 }}>({it.unit})</span>
                )}
              </td>
              <td className="r" style={{ color: "var(--muted)" }}>{fmt(it.prev)}</td>
              <td className="r">{fmt(it.suggested)}</td>
              <td className="r" style={{ color: it.action ? ACTION_COLOR[it.action] : "var(--muted)", fontWeight: 600, whiteSpace: "nowrap" }}>
                {it.delta == null ? "—" : (
                  <>{sInt(it.delta)}<span style={{ fontSize: 11, marginLeft: 4, opacity: 0.85 }}>
                    ({it.delta_pct == null ? "—" : (it.delta_pct > 0 ? "+" : "") + it.delta_pct + "%"})
                  </span></>
                )}
              </td>
              <td><ActionTag action={it.action} /></td>
              <td className="r" style={{ color: "var(--muted)" }}>{fmt(it.actual)}</td>
              <td className="r"><ConfTag c={it.confidence} /></td>
            </tr>
          ))}
          {!items.length && (
            <tr><td colSpan={7} style={{ textAlign: "center", padding: 18, color: "var(--muted)" }}>Chọn lần ban hành.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
