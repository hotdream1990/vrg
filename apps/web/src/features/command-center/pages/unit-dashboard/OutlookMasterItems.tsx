/* Bảng nhỏ "HĐ dài hạn (HĐDH) có cam kết sản lượng" — chỉ khi xem MỘT đơn vị. Giữ thứ tự server (còn
   phải giao giảm dần). Chỉ có HĐDH (HĐ nguyên tắc không tính) nên không cần cột Loại. HĐDH đã hết hạn: còn lại = 0 (phần thiếu không tính vào phải giao) → gắn nhãn. */

import { dmy } from "../../../../lib/date";
import type { BacklogItem } from "../../../../lib/sales-contract-client";
import { fmtTon } from "./dashboard-format";
import { MiniPct } from "./OutlookBars";

export default function OutlookMasterItems({ items }: { items: BacklogItem[] }) {
  return (
    <>
      <div className="ud-mini-title">
        HĐ dài hạn (HĐDH) có cam kết sản lượng ({items.length.toLocaleString("vi-VN")})
      </div>
      {/* Cuộn dọc trong khung khi đơn vị có nhiều HĐDH — tiêu đề cột ghim trên. */}
      <div className="ud-table-wrap ud-scroll">
        <table className="ud-table ud-ol-table">
          <thead>
            <tr>
              <th>Số HĐDH</th>
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
