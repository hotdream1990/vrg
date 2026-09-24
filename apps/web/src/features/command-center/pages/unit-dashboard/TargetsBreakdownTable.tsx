/* Bảng "Tiến độ theo khu vực / đơn vị" dưới card Chỉ tiêu năm: 3 cột % lũy kế, mỗi ô một thanh mini.
   Ô chậm hơn tiến độ thời gian quá 10 điểm % tô vàng để nhìn ra ai chậm. Giữ thứ tự dòng server trả
   (cùng thứ tự khu vực/đơn vị như các màn khác) — không tự sắp lại. */

import type { TargetsBlock } from "../../../../lib/unit-dashboard-client";
import { fmtPct, isBehind } from "./dashboard-format";

type Row = TargetsBlock["breakdown"][number];

type Props = {
  rows: Row[];
  timePct: number;
  childLabel: string;
};

const COLS: { field: keyof Omit<Row, "label">; label: string }[] = [
  { field: "purchase_pct", label: "Thu mua" },
  { field: "sales_spot_pct", label: "Tiêu thụ HĐ chuyến" },
  { field: "revenue_pct", label: "Doanh thu" },
];

function PctCell({ pct, timePct }: { pct: number | null; timePct: number }) {
  if (pct == null) return <td className="r ud-muted">—</td>;
  const behind = isBehind(pct, timePct);
  return (
    <td className={`r${behind ? " ud-warn" : ""}`}>
      <div className="ud-pct-cell">
        <span className="ud-mini-bar">
          <span className={behind ? "is-behind" : ""} style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }} />
        </span>
        <span className="ud-pct-text">{fmtPct(pct)}</span>
      </div>
    </td>
  );
}

export default function TargetsBreakdownTable({ rows, timePct, childLabel }: Props) {
  return (
    <div className="ud-table-wrap">
      <div className="ud-mini-title">
        Tiến độ theo {childLabel.toLowerCase()}
        <span className="ud-muted"> · ô vàng = chậm hơn tiến độ thời gian ({fmtPct(timePct)}) quá 10 điểm %</span>
      </div>
      <table className="ud-table">
        <thead>
          <tr>
            <th>{childLabel}</th>
            {COLS.map((c) => <th key={c.field} className="r">{c.label} (%)</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <td>{r.label}</td>
              {COLS.map((c) => <PctCell key={c.field} pct={r[c.field]} timePct={timePct} />)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
