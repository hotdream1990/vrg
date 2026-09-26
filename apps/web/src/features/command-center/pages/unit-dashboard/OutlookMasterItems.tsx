/* Bảng nhỏ "Hợp đồng mẹ có cam kết sản lượng" — chỉ khi xem MỘT đơn vị. Giữ thứ tự server (còn phải
   giao giảm dần). HĐ mẹ đã hết hạn: còn lại = 0 (phần thiếu không tính vào phải giao) → gắn nhãn. */

import { dmy } from "../../../../lib/date";
import type { BacklogItem } from "../../../../lib/sales-contract-client";
import { fmtTon } from "./dashboard-format";
import { MiniPct } from "./OutlookBars";

const TYPE_LABEL: Record<string, string> = { principle: "HĐNT", long_term: "HĐDH" };

export default function OutlookMasterItems({ items }: { items: BacklogItem[] }) {
  return (
    <>
      <div className="ud-mini-title">
        Hợp đồng mẹ có cam kết sản lượng ({items.length.toLocaleString("vi-VN")})
      </div>
      {/* Cuộn dọc trong khung khi đơn vị có nhiều HĐ mẹ — tiêu đề cột ghim trên. */}
      <div className="ud-table-wrap ud-scroll">
        <table className="ud-table ud-ol-table">
          <thead>
            <tr>
              <th>Số HĐ mẹ</th>
              <th>Loại</th>
              <th>Hiệu lực</th>
              <th className="r">Cam kết (tấn)</th>
              <th className="r">Đã giao (tấn)</th>
              <th className="r">Còn lại (tấn)</th>
              <th className="r">% thực hiện</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.id}>
                <td>
                  {it.code || `#${it.id}`}
                  {it.expired && <span className="db-badge warn ud-badge-gap">hết hạn</span>}
                </td>
                <td>{TYPE_LABEL[it.master_type] ?? it.master_type}</td>
                <td>
                  {it.sign_date ? dmy(it.sign_date) : "—"} → {it.expiry_date ? dmy(it.expiry_date) : "không thời hạn"}
                </td>
                <td className="r">{fmtTon(it.committed)}</td>
                <td className="r">{fmtTon(it.delivered)}</td>
                <td className="r">{fmtTon(it.remaining)}</td>
                <td className="r"><MiniPct pct={it.pct} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
