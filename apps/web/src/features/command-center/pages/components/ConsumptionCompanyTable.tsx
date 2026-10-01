import type { ConsumptionReport, ContractMeta } from "../../../../lib/sales-contract-client";
import {
  type BacklogTotals, type ConsumptionTotals, t3, ty, wet,
} from "./consumption-report-totals";

type Props = {
  rep: ConsumptionReport | null;
  meta: ContractMeta | null;
  companies: string[];
  totals: ConsumptionTotals;
  backlog: BacklogTotals | null;
  loading: boolean;
};

/** Bảng tiêu thụ theo đơn vị. Có `backlog` → 4 cột phải giao (HĐ chuyến · HĐNT · HĐ dài hạn · tổng), thêm
 *  cột "HĐ chưa khai loại" khi có — tách giống file Excel để web và file cùng một số;
 *  API cũ → 1 cột "Chưa giao" (khối 3) như trước. */
export default function ConsumptionCompanyTable({ rep, meta, companies, totals, backlog, loading }: Props) {
  const rows = rep?.by_company ?? {};
  const undelivered = rep?.undelivered ?? {};
  const bl = rep?.backlog;
  const ch = (c: string, k: string) => rows[c]?.by_channel?.[k] ?? 0;
  const unknownCol = !!backlog && backlog.unknown > 0;
  const cols = (bl ? 12 : 9) + (unknownCol ? 1 : 0);

  return (
    <div className="card table-scroll" style={{ padding: 0 }}>
      <table>
        <thead><tr>
          <th>Đơn vị</th><th className="r">Lần giao</th><th className="r">Quy khô (tấn)</th>
          {/* Số chưa quy khô để đối chiếu số cân thực tế — chỉ chủng loại còn nước mới có. */}
          <th className="r">SL chưa quy khô (tấn)</th>
          <th className="r">{meta?.channels.export ?? "Xuất khẩu"}</th>
          <th className="r">{meta?.channels.domestic ?? "Trong nước"}</th>
          <th className="r">{meta?.channels.internal ?? "Nội bộ"}</th>
          <th className="r">Doanh thu (tỷ đ)</th>
          {bl ? (
            <>
              <th className="r">HĐ chuyến chưa giao (tấn)</th>
              <th className="r">HĐNT đã ký chưa giao (tấn)</th>
              <th className="r">HĐ dài hạn còn phải giao (tấn)</th>
              {unknownCol && <th className="r">HĐ chưa khai loại chưa giao (tấn)</th>}
              <th className="r">Tổng phải giao (tấn)</th>
            </>
          ) : <th className="r">Chưa giao (tấn quy khô)</th>}
        </tr></thead>
        <tbody>
          {companies.map((c) => (
            <tr key={c}>
              <td style={{ fontWeight: 500 }}>{c}</td>
              <td className="r">{rows[c]?.deliveries ?? 0}</td>
              <td className="r">{t3(rows[c]?.qty ?? 0)}</td>
              <td className="r">{wet(rows[c]?.qty_wet ?? 0)}</td>
              <td className="r">{t3(ch(c, "export"))}</td>
              <td className="r">{t3(ch(c, "domestic"))}</td>
              <td className="r">{t3(ch(c, "internal"))}</td>
              <td className="r">{ty(rows[c]?.revenue ?? null)}</td>
              {bl ? (
                <>
                  <td className="r">{t3(bl[c]?.spot_undelivered ?? 0)}</td>
                  <td className="r">{t3(bl[c]?.principle_undelivered ?? 0)}</td>
                  <td className="r">{t3(bl[c]?.lt_remaining ?? 0)}</td>
                  {unknownCol && <td className="r">{t3(bl[c]?.unknown_undelivered ?? 0)}</td>}
                  <td className="r" style={{ fontWeight: 600 }}>{t3(bl[c]?.to_deliver ?? 0)}</td>
                </>
              ) : <td className="r">{t3(undelivered[c]?.qty ?? 0)}</td>}
            </tr>
          ))}
          {companies.length === 0 && !loading && (
            <tr><td colSpan={cols} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
              Chưa có lần giao nào trong kỳ — nới rộng khoảng ngày hoặc bỏ bớt bộ lọc.
            </td></tr>
          )}
        </tbody>
        {companies.length > 0 && (
          <tfoot>
            <tr style={{ fontWeight: 600 }}>
              <td>
                Lũy kế cả kỳ
                <span style={{ fontWeight: 400, color: "var(--muted)", fontSize: 12 }}>
                  {" "}· {companies.length} đơn vị
                </span>
              </td>
              <td className="r">{totals.deliveries.toLocaleString("vi-VN")}</td>
              <td className="r">{t3(totals.qty)}</td>
              <td className="r">{wet(totals.qty_wet)}</td>
              <td className="r">{t3(totals.channels.export)}</td>
              <td className="r">{t3(totals.channels.domestic)}</td>
              <td className="r">{t3(totals.channels.internal)}</td>
              <td className="r">{ty(totals.revenue)}</td>
              {backlog ? (
                <>
                  <td className="r">{t3(backlog.spot)}</td>
                  <td className="r">{t3(backlog.principle)}</td>
                  <td className="r">{t3(backlog.lt)}</td>
                  {unknownCol && <td className="r">{t3(backlog.unknown)}</td>}
                  <td className="r">{t3(backlog.toDeliver)}</td>
                </>
              ) : <td className="r">{t3(totals.remaining)}</td>}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}
