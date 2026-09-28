import { dmy } from "../../../../lib/date";
import type { BacklogItem } from "../../../../lib/sales-contract-client";
import { pct1, t3 } from "./consumption-report-totals";

/** Thanh mini + số % thực hiện (thanh đầy ở 100%, số vẫn hiện số thật nếu giao vượt cam kết). */
export function PctBar({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="cmp-pct-text">—</span>;
  return (
    <span className="cmp-pct">
      <span className="cmp-bar"><span style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }} /></span>
      <span className="cmp-pct-text">{pct1(pct)}</span>
    </span>
  );
}

type Props = {
  items: BacklogItem[];
  /** Tên khách theo id — lấy từ `customers` của báo cáo; không tra được thì bỏ cột khách. */
  customers: Record<string, string>;
};

/** Danh sách HĐDH có cam kết của MỘT đơn vị — mở ra khi bấm dòng đơn vị. Giữ thứ tự server
 *  (còn phải giao giảm dần). Chỉ có HĐDH (HĐ nguyên tắc không tính) nên không cần cột Loại. */
export default function ConsumptionMasterItems({ items, customers }: Props) {
  const nameOf = (id: number | null) => (id == null ? undefined : customers[String(id)]);
  const showCustomer = items.some((it) => nameOf(it.customer_id));
  return (
    <table className="cmp-items">
      <thead><tr>
        <th>Số HĐDH</th>
        {showCustomer && <th>Khách hàng</th>}
        <th>Hiệu lực</th>
        <th className="r">Cam kết (tấn)</th><th className="r">Đã giao (tấn)</th>
        <th className="r">Còn lại (tấn)</th><th className="r">% thực hiện</th>
      </tr></thead>
      <tbody>
        {items.map((it) => (
          <tr key={it.id}>
            <td style={{ fontWeight: 500 }}>
              {it.code || `#${it.id}`}
              {it.expired && <span className="db-badge warn cmp-expired">hết hạn</span>}
            </td>
            {showCustomer && <td>{nameOf(it.customer_id) ?? "—"}</td>}
            <td>{dmy(it.sign_date)} → {it.expiry_date ? dmy(it.expiry_date) : "không thời hạn"}</td>
            <td className="r">{t3(it.committed)}</td>
            <td className="r">{t3(it.delivered)}</td>
            <td className="r">{t3(it.remaining)}</td>
            <td className="r"><PctBar pct={it.pct} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
