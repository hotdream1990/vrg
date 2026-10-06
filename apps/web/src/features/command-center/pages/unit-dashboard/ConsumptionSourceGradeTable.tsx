/* Cơ cấu NGUỒN tiêu thụ theo CHỦNG LOẠI: mỗi chủng loại tách khai thác · thu mua · hàng hóa cao su
   (tấn quy khô) + tỷ trọng trong chính chủng loại đó (thanh mini). Dòng Tổng cộng lấy `totals` server
   trả → tỷ trọng từng nguồn trên toàn kỳ. Ẩn khi API cũ (không có khoá nguồn) hoặc chưa có số. */

import type { ConsumptionBlock } from "../../../../lib/unit-dashboard-client";
import { SOURCE_LABELS } from "../components/consumption-source-labels";
import { SOURCE_PARTS, hasSourceKeys, sourceSum } from "./consumption-sources";
import { type Num, differsNotably, fmtPct, fmtTon, fmtTons, share, sortDesc } from "./dashboard-format";

type Props = { rows: ConsumptionBlock["by_grade"]; totals: ConsumptionBlock["totals"] };

function SourceCell({ qty, total, color }: { qty: Num; total: Num; color: string }) {
  const pct = share(qty, total);
  return (
    <td className="r">
      <div className="ud-pct-cell">
        <span className={qty ? undefined : "ud-muted"}>{fmtTon(qty)}</span>
        <span className="ud-mini-bar">
          <span style={{ width: `${Math.min(Math.max(pct ?? 0, 0), 100)}%`, background: color }} />
        </span>
        <span className="ud-pct-text ud-muted">{fmtPct(pct)}</span>
      </div>
    </td>
  );
}

export default function ConsumptionSourceGradeTable({ rows, totals }: Props) {
  const grand = sourceSum(totals);
  if (!hasSourceKeys(totals) || grand == null || grand <= 0) return null;

  const list = sortDesc(rows.map((r) => ({ ...r, total: sourceSum(r) })), (r) => r.total)
    .filter((r) => r.total != null && r.total > 0);
  // Dòng mang mã nguồn lạ không vào ô nào → nói rõ phần hụt, khỏi tưởng bảng lệch với tổng tiêu thụ.
  const unsourced = totals.qty != null && differsNotably(grand, totals.qty) ? totals.qty - grand : null;

  return (
    <div className="ud-table-wrap">
      <div className="ud-mini-title">
        Cơ cấu nguồn tiêu thụ theo chủng loại
        <span className="ud-muted"> · tấn quy khô · % = tỷ trọng của nguồn trong từng chủng loại</span>
      </div>
      <table className="ud-table">
        <thead>
          <tr>
            <th>Chủng loại</th>
            {SOURCE_PARTS.map((p) => <th key={p.key} className="r">{p.label} (tấn · %)</th>)}
            <th className="r">Tổng (tấn quy khô)</th>
          </tr>
        </thead>
        <tbody>
          {list.map((r) => (
            <tr key={r.grade}>
              <td>{r.grade}</td>
              {SOURCE_PARTS.map((p) => (
                <SourceCell key={p.key} qty={r[p.key]} total={r.total} color={p.color} />
              ))}
              <td className="r">{fmtTon(r.total)}</td>
            </tr>
          ))}
          <tr className="ud-total">
            <td>Tổng cộng</td>
            {SOURCE_PARTS.map((p) => (
              <SourceCell key={p.key} qty={totals[p.key]} total={grand} color={p.color} />
            ))}
            <td className="r">{fmtTon(grand)}</td>
          </tr>
        </tbody>
      </table>
      <p className="ud-note">
        Nguồn khai theo từng dòng chủng loại của lần giao; lần giao nhập trước khi có ô nguồn được tính
        là {SOURCE_LABELS.exploit.toLowerCase()}.
        {unsourced != null && unsourced > 0 && ` Còn ${fmtTons(unsourced)} chưa xác định nguồn nên không có trong bảng.`}
      </p>
    </div>
  );
}
