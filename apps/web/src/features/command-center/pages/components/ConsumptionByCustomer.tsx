import type { ConsumptionReport } from "../../../../lib/sales-contract-client";

const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });
const ty = (n: number) => (n / 1_000_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 3 });

type Row = { key: string; name: string; company: string; qty: number; revenue: number };

/** Tiêu thụ tách theo KHÁCH HÀNG (yêu cầu C1) — khách gán ở hợp đồng, đợt giao kế thừa.
    Danh mục khách tách riêng theo đơn vị nên luôn kèm tên đơn vị, tránh 2 dòng trùng tên. */
export default function ConsumptionByCustomer({ rep }: { rep: ConsumptionReport }) {
  const rows: Row[] = [];
  for (const [company, c] of Object.entries(rep.by_company)) {
    for (const [id, v] of Object.entries(c.by_customer ?? {})) {
      if (!v.qty && !v.revenue) continue;
      rows.push({
        key: `${company}|${id}`, company, qty: v.qty, revenue: v.revenue,
        // id "0" = lần giao thuộc hợp đồng chưa gán khách (dữ liệu chuyển đổi từ hệ cũ).
        name: rep.customers[id] ?? (id === "0" ? "(chưa gán khách hàng)" : `#${id}`),
      });
    }
  }
  rows.sort((a, b) => b.qty - a.qty);
  if (!rows.length) return null;

  // Lũy kế của cả khối — để đối chiếu ngay với bảng theo đơn vị phía trên (hai bảng cùng một kỳ,
  // cùng bộ lọc nên tổng phải bằng nhau; lệch là dấu hiệu có lần giao chưa gán khách).
  const sumQty = rows.reduce((a, r) => a + r.qty, 0);
  const sumRevenue = rows.reduce((a, r) => a + r.revenue, 0);

  return (
    <>
      <div className="blt-toolbar" style={{ marginTop: 14 }}>
        <b>Theo khách hàng</b>
        <span style={{ color: "var(--muted)", fontSize: 13 }}>{rows.length} dòng</span>
      </div>
      <div className="card table-scroll" style={{ padding: 0 }}>
        <table>
          <thead><tr>
            <th>Khách hàng</th><th>Đơn vị</th>
            <th className="r">Sản lượng (tấn)</th><th className="r">Doanh thu (tỷ đ)</th>
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key}>
                <td style={{ fontWeight: 500 }}>{r.name}</td>
                <td>{r.company}</td>
                <td className="r">{t3(r.qty)}</td>
                <td className="r">{ty(r.revenue)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr style={{ fontWeight: 600 }}>
              <td colSpan={2}>Lũy kế cả kỳ</td>
              <td className="r">{t3(sumQty)}</td>
              <td className="r">{ty(sumRevenue)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  );
}
