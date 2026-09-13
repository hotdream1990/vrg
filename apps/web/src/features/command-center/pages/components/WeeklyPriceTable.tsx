/* Bảng giá III.1 (sàn quốc tế) / III.2 (giao ngay) — số tự tính, chỉ đọc.
   Mọi kỳ (1–3 tuần) bám mẫu 35–36: mỗi tuần 1 cột (giá 1 số lẻ) + mỗi cặp liền nhau 1 cột
   "+/- (T35/T34)" có dấu, in đậm; không cột % (% xem ở tooltip ô +/-). */

import type { WeekCol, WeekTableRow } from "../../../../lib/weekly-report-client";
import { pairLabel, signed, vn } from "./WeeklyFormat";

const EXCHANGE_ORDER = ["OSE", "SHANGHAI", "SGX", "MRE"];

type Props = {
  rows: WeekTableRow[];
  weeks: WeekCol[];
  /** true = bảng III.1 (có cột Sàn, gộp dòng theo sàn). */
  withExchange: boolean;
};

/** Gom dòng theo sàn đúng thứ tự mẫu; sàn lạ (nếu có) xếp cuối — không được làm rơi dòng. */
function groupRows(rows: WeekTableRow[]) {
  const names = [...EXCHANGE_ORDER, ...new Set(rows.map((r) => r.exchange ?? "").filter((e) => !EXCHANGE_ORDER.includes(e)))];
  return names
    .map((exchange) => ({ exchange, items: rows.filter((r) => (r.exchange ?? "") === exchange) }))
    .filter((g) => g.items.length);
}

export default function WeeklyPriceTable({ rows, weeks, withExchange }: Props) {
  const shorts = weeks.map((w) => w.short || `T${w.week_no}`);
  const groups = withExchange ? groupRows(rows) : [{ exchange: "", items: rows }];

  return (
    <div className="wk-scroll">
      <table className="wk-table">
        <thead>
          <tr>
            {withExchange && <th>Sàn</th>}<th>SP</th>
            {weeks.map((w) => <th key={w.mon}>{w.label}</th>)}
            {weeks.slice(1).map((_, i) => <th key={i}>{pairLabel(shorts, i + 1)}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr><td colSpan={20} className="c wk-muted">Chưa có số liệu trong kỳ.</td></tr>
          )}
          {groups.map((g) => g.items.map((r, j) => (
            <tr key={`${g.exchange}-${r.grade}`}>
              {withExchange && j === 0 && <td className="c wk-strong" rowSpan={g.items.length}>{g.exchange}</td>}
              <td className="c">{r.grade}</td>
              {weeks.map((w, i) => <td key={w.mon} className="r">{vn(r.values?.[i] ?? null, 1)}</td>)}
              {weeks.slice(1).map((_, i) => (
                <td key={i} className="r wk-chg" title={r.changes_pct?.[i] != null ? signed(r.changes_pct[i], 2, "%") : ""}>
                  {signed(r.changes?.[i] ?? null, 1)}
                </td>
              ))}
            </tr>
          )))}
        </tbody>
      </table>
    </div>
  );
}
