/* Báo cáo tiêu thụ — bảng "Tiêu thụ theo nguồn × chủng loại": cộng `by_source_grade` của ĐÚNG các
   đơn vị đang hiện ở bảng theo đơn vị (cùng danh sách `companies`) → tổng mỗi nguồn khớp cột "Nguồn …"
   ở dòng Lũy kế phía trên. Web chỉ CỘNG số server đã tính (tấn quy khô), không tự suy số nào khác.
   Ẩn khi API cũ (không có `by_source_grade`) hoặc kỳ này chưa có số. */

import { Fragment } from "react";

import type { ConsumptionReport, ContractMeta } from "../../../../lib/sales-contract-client";
import { SOURCE_KEYS, type SourceKey, sourceLabel } from "./consumption-source-labels";
import { pct1, t3 } from "./consumption-report-totals";

type Props = { rep: ConsumptionReport; meta: ContractMeta | null; companies: string[] };
type Row = { grade: string; bySource: Record<SourceKey, number>; total: number };

const NO_GRADE = "(chưa khai chủng loại)";
const MUTED = { color: "var(--muted)" } as const;

const zeroSources = (): Record<SourceKey, number> => ({ exploit: 0, purchase: 0, goods: 0 });
const sumSources = (v: Record<SourceKey, number>) => SOURCE_KEYS.reduce((a, s) => a + v[s], 0);

/** null = không đơn vị nào có `by_source_grade` (API cũ). */
function buildRows(rep: ConsumptionReport, companies: string[]): Row[] | null {
  const acc = new Map<string, Record<SourceKey, number>>();
  let hasKey = false;
  for (const c of companies) {
    const m = rep.by_company[c]?.by_source_grade;
    if (!m) continue;
    hasKey = true;
    for (const s of SOURCE_KEYS) {
      for (const [grade, qty] of Object.entries(m[s] ?? {})) {
        const cur = acc.get(grade) ?? zeroSources();
        acc.set(grade, { ...cur, [s]: cur[s] + (qty || 0) });
      }
    }
  }
  if (!hasKey) return null;
  return Array.from(acc, ([grade, bySource]) => ({ grade, bySource, total: sumSources(bySource) }))
    .filter((r) => r.total > 0)
    .sort((a, b) => b.total - a.total);
}

/** 2 ô của một nguồn: tấn · % trong hàng. Ô 0 tô mờ cho dễ nhìn ra nguồn thật sự có hàng. */
function SourceCells({ qty, total }: { qty: number; total: number }) {
  const style = qty ? undefined : MUTED;
  return (
    <>
      <td className="r" style={style}>{t3(qty)}</td>
      <td className="r" style={{ ...MUTED, fontSize: 12 }}>{pct1(total > 0 ? (qty / total) * 100 : null)}</td>
    </>
  );
}

export default function ConsumptionSourceGradeMatrix({ rep, meta, companies }: Props) {
  const rows = buildRows(rep, companies);
  if (!rows?.length) return null;
  const colTotal = rows.reduce((acc, r) => {
    for (const s of SOURCE_KEYS) acc[s] += r.bySource[s];
    return acc;
  }, zeroSources());
  const grand = sumSources(colTotal);

  return (
    <>
      <div className="blt-toolbar" style={{ marginTop: 14 }}>
        <b>Tiêu thụ theo nguồn × chủng loại</b>
        <span style={{ ...MUTED, fontSize: 13 }}>
          tấn quy khô · % = tỷ trọng của nguồn trong từng chủng loại · cùng {companies.length} đơn vị
          của bảng trên
        </span>
      </div>
      {/* Không dùng `table-scroll`: tiêu đề 2 tầng mà dính đầu bảng thì tầng dưới đè lên tầng trên. */}
      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table>
          <thead>
            <tr>
              <th rowSpan={2}>Chủng loại</th>
              {SOURCE_KEYS.map((s) => (
                <th key={s} colSpan={2} style={{ textAlign: "center" }}>
                  Nguồn {sourceLabel(s, meta?.sources).toLowerCase()}
                </th>
              ))}
              <th rowSpan={2} className="r">Tổng (tấn)</th>
            </tr>
            <tr>
              {SOURCE_KEYS.map((s) => (
                <Fragment key={s}><th className="r">Tấn</th><th className="r">%</th></Fragment>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.grade}>
                <td style={{ fontWeight: 500 }}>{r.grade || NO_GRADE}</td>
                {SOURCE_KEYS.map((s) => <SourceCells key={s} qty={r.bySource[s]} total={r.total} />)}
                <td className="r" style={{ fontWeight: 600 }}>{t3(r.total)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr style={{ fontWeight: 600 }}>
              <td>Tổng cộng</td>
              {SOURCE_KEYS.map((s) => <SourceCells key={s} qty={colTotal[s]} total={grand} />)}
              <td className="r">{t3(grand)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  );
}
