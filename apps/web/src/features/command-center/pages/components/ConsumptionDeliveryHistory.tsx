import { useEffect, useState } from "react";

import { dmy } from "../../../../lib/date";
import {
  type DeliveryHistory,
  fetchConsumptionDeliveries,
} from "../../../../lib/sales-contract-client";

const PAGE_SIZE = 50;

const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });
const ty = (n: number | null) =>
  (n == null ? "—" : (n / 1_000_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));

type Props = {
  from: string;
  to: string;
  company?: string;
  customerIds: number[];
  grades: string[];
};

/** LỊCH SỬ TỪNG LẦN GIAO đứng sau bảng tổng hợp — để soát lại chi tiết, không phải nhập liệu.
 *
 *  Cùng bộ lọc với bảng tổng hợp nên tổng mọi trang khớp đúng con số phía trên. Phân trang ở
 *  SERVER: prod đã hơn 3.000 lần giao, kéo hết về máy là treo màn hình.
 */
export default function ConsumptionDeliveryHistory(p: Props) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<DeliveryHistory | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  // Đổi bộ lọc thì phải về trang 1: đang ở trang 5 mà lọc còn 2 trang là bảng trống trơn.
  useEffect(() => { setPage(1); }, [p.from, p.to, p.company, p.customerIds, p.grades]);

  useEffect(() => {
    if (!p.from || !p.to) return;
    let cancelled = false;
    setLoading(true); setErr("");
    fetchConsumptionDeliveries(p.from, p.to, p.company, p.customerIds, p.grades, page, PAGE_SIZE)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setErr(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [p.from, p.to, p.company, p.customerIds, p.grades, page]);

  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const first = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const last = Math.min(page * PAGE_SIZE, total);

  return (
    <>
      <div className="blt-toolbar" style={{ marginTop: 14 }}>
        <b>Lịch sử đợt giao</b>
        <span style={{ color: "var(--muted)", fontSize: 13 }}>
          {loading ? "Đang tải…" : total === 0 ? "Chưa có lần giao nào" : `${first}–${last} / ${total} lần giao`}
        </span>
        {pages > 1 && (
          <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
            <button className="btn" disabled={page <= 1 || loading}
              onClick={() => setPage((n) => Math.max(1, n - 1))}>Trước</button>
            <span style={{ color: "var(--muted)", fontSize: 13 }}>Trang {page}/{pages}</span>
            <button className="btn" disabled={page >= pages || loading}
              onClick={() => setPage((n) => Math.min(pages, n + 1))}>Sau</button>
          </span>
        )}
      </div>

      {err && <div className="blt-error">{err}</div>}

      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table>
          <thead><tr>
            <th>Ngày giao</th><th>Đơn vị</th><th>Số hợp đồng</th><th>Đợt</th>
            <th>Khách hàng</th><th>Loại HĐ</th><th>Hình thức</th><th>Chủng loại</th>
            <th className="r">SL (tấn)</th><th className="r">Quy khô</th>
            <th className="r">Doanh thu (tỷ đ)</th><th>Số hoá đơn</th>
          </tr></thead>
          <tbody>
            {(data?.rows ?? []).map((r) => (
              <tr key={r.id}>
                <td>{dmy(r.delivered_at)}</td>
                <td>{r.company}</td>
                <td style={{ fontWeight: 500 }}>{r.contract_code || "—"}</td>
                {/* Trống = hợp đồng giao trọn 1 lần, không chia đợt */}
                <td>{r.batch_code ?? "—"}</td>
                <td>{r.customer_name ?? "(chưa gán khách hàng)"}</td>
                <td>{r.contract_type ?? "—"}</td>
                <td>{r.channel ?? "—"}</td>
                <td>{r.grades || "—"}</td>
                <td className="r">{t3(r.qty)}</td>
                <td className="r">{t3(r.qty_dry)}</td>
                <td className="r">{ty(r.revenue)}</td>
                <td>{r.invoice_no ?? "—"}</td>
              </tr>
            ))}
            {total === 0 && !loading && (
              <tr><td colSpan={12} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                Chưa có lần giao nào trong kỳ — nới rộng khoảng ngày hoặc bỏ bớt bộ lọc.
              </td></tr>
            )}
          </tbody>
          {/* Lũy kế do SERVER cộng trên MỌI trang của kỳ — nói rõ trên nhãn, vì bảng có phân trang
              nên người đọc rất dễ hiểu nhầm là tổng của 50 dòng đang thấy. */}
          {data && data.rows.length > 0 && (
            <tfoot>
              <tr style={{ fontWeight: 600 }}>
                <td colSpan={8}>
                  Lũy kế cả kỳ
                  <span style={{ fontWeight: 400, color: "var(--muted)", fontSize: 12 }}>
                    {" "}· {total.toLocaleString("vi-VN")} lần giao
                    {pages > 1 && " (không chỉ trang này)"}
                  </span>
                </td>
                <td className="r">{t3(data.totals.qty)}</td>
                <td className="r">{t3(data.totals.qty_dry)}</td>
                <td className="r">{ty(data.totals.revenue)}</td>
                <td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </>
  );
}
