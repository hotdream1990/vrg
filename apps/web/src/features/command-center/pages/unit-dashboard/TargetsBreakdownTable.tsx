/* Bảng "Tiến độ theo khu vực / đơn vị" dưới card Chỉ tiêu năm: mỗi chỉ tiêu một cột % lũy kế, mỗi ô
   một thanh mini. Cột Hàng hóa chỉ hiện khi có dòng được giao KH (đa số đơn vị không kinh doanh).
   Ô thấp hơn tiến độ thời gian quá 10 điểm % tô vàng — chỉ là LƯU Ý: vạch chia đều theo ngày, chưa tính
   mùa vụ (xem TargetsCard) nên không được nói là "đơn vị chậm kế hoạch". Giữ thứ tự dòng server trả
   (cùng thứ tự khu vực/đơn vị như các màn khác) — không tự sắp lại. */

import type { TargetsBlock } from "../../../../lib/unit-dashboard-client";
import { fmtPct, isBehind } from "./dashboard-format";

type Row = TargetsBlock["breakdown"][number];

/** Giải thích vạch tiến độ thời gian — dùng chung với thẻ Chỉ tiêu năm (tiêu đề, tooltip). */
export const TIME_MARK_NOTE = "chia đều theo ngày, chưa tính mùa vụ (đầu năm nghỉ cạo nên thu "
  + "mua/tiêu thụ thường thấp hơn vạch)";

/** Ô/số % tô vàng — cảnh báo nhẹ, KHÔNG phải kết luận "đơn vị chậm kế hoạch". */
export const BEHIND_HINT = "Thấp hơn vạch tiến độ thời gian quá 10 điểm % — chỉ để lưu ý, chưa đủ để "
  + "kết luận chậm kế hoạch";

type Props = {
  rows: Row[];
  timePct: number;
  childLabel: string;
};

const COLS: { field: keyof Omit<Row, "label">; label: string }[] = [
  { field: "purchase_pct", label: "Thu mua" },
  { field: "goods_pct", label: "Hàng hóa" },
  { field: "sales_spot_pct", label: "Tiêu thụ HĐ chuyến" },
  { field: "revenue_pct", label: "Doanh thu" },
];

function PctCell({ pct, timePct }: { pct: number | null; timePct: number }) {
  if (pct == null) return <td className="r ud-muted">—</td>;
  const behind = isBehind(pct, timePct);
  return (
    <td className={`r${behind ? " ud-warn" : ""}`}
        title={behind ? `${BEHIND_HINT}.` : undefined}>
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
  const cols = COLS.filter((c) => c.field !== "goods_pct" || rows.some((r) => r.goods_pct != null));
  return (
    <div className="ud-table-wrap">
      <div className="ud-mini-title">
        Tiến độ theo {childLabel.toLowerCase()}
        <span className="ud-muted"> · ô vàng = thấp hơn tiến độ thời gian ({fmtPct(timePct)}) quá 10 điểm %,
          chỉ để lưu ý: vạch {TIME_MARK_NOTE}.</span>
      </div>
      <table className="ud-table">
        <thead>
          <tr>
            <th>{childLabel}</th>
            {cols.map((c) => <th key={c.field} className="r">{c.label} (%)</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <td>{r.label}</td>
              {cols.map((c) => <PctCell key={c.field} pct={r[c.field]} timePct={timePct} />)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
