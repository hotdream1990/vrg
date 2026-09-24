/* Bảng tiêu thụ theo CHỦNG LOẠI (thành phẩm): sản lượng · doanh thu · giá bán BQ + thanh tỷ trọng
   sản lượng. Tỷ trọng tính trên tổng sản lượng server trả (không tự cộng lại các dòng). */

import type { ConsumptionBlock } from "../../../../lib/unit-dashboard-client";
import { fmtPct, fmtPrice, fmtTon, fmtTy } from "./dashboard-format";

type Props = { rows: ConsumptionBlock["by_grade"]; totalQty: number | null };

const share = (qty: number | null, total: number | null): number | null =>
  qty == null || total == null || total <= 0 ? null : (qty / total) * 100;

export default function ConsumptionGradeTable({ rows, totalQty }: Props) {
  if (!rows.length) return <div className="scan-empty">Chưa có số tiêu thụ theo chủng loại.</div>;
  return (
    <div className="ud-table-wrap ud-scroll">
      <table className="ud-table">
        <thead>
          <tr>
            <th>Chủng loại</th>
            <th className="r">SL (tấn)</th>
            <th className="r">Doanh thu (tỷ đ)</th>
            <th className="r">Giá BQ (tr.đ/tấn)</th>
            <th className="r">Tỷ trọng</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const pct = share(r.qty, totalQty);
            return (
              <tr key={r.grade}>
                <td>{r.grade}</td>
                <td className="r">{fmtTon(r.qty)}</td>
                <td className="r">{fmtTy(r.revenue_ty)}</td>
                <td className="r">{fmtPrice(r.avg_price_trieu, "triệu đ/tấn")}</td>
                <td className="r">{pct == null ? <span className="ud-muted">—</span> : fmtPct(pct)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
