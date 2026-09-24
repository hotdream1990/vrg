/* Bảng bản lưu số liệu tuần — mỗi đơn vị 1 dòng, 3 nhóm cột Thu mua · Tiêu thụ · Tồn kho,
   cuối bảng là dòng Tổng cộng LẤY TỪ BẢN LƯU (server cộng lúc chụp, không cộng lại ở đây).
   Cột + công thức bám đúng màn Báo cáo tổng hợp (cùng nguồn `period_report`). */

import type { PeriodRow } from "../../../lib/unit-daily-client";
import { dmy } from "../../../lib/date";
import { displayDigits, fmtNum } from "../../../lib/unit-daily-fields";
import type { SnapshotDetail, SnapshotTotals } from "../../../lib/unit-week-snapshot-client";

type Src = "purchase" | "consumption";
type Col = { src: Src; key: string; label: string; unit: string; date?: boolean; noSum?: boolean };
type Group = { label: string; cols: Col[] };

const GROUPS: Group[] = [
  { label: "Thu mua (quy khô)", cols: [
    { src: "purchase", key: "latex_wet", label: "Mủ nước", unit: "tấn" },
    { src: "purchase", key: "coagulum", label: "Mủ chén", unit: "tấn" },
    { src: "purchase", key: "lace", label: "Mủ dây", unit: "tấn" },
    { src: "purchase", key: "total_purchase", label: "Tổng thu mua", unit: "tấn" },
    { src: "purchase", key: "finished_qty", label: "Thu mua thành phẩm", unit: "tấn" },
    { src: "purchase", key: "pct_plan", label: "% KH năm", unit: "%", noSum: true },
  ] },
  { label: "Tiêu thụ (theo hợp đồng)", cols: [
    { src: "consumption", key: "total_consumption", label: "Tổng tiêu thụ", unit: "tấn" },
    { src: "consumption", key: "export_total", label: "XK/UTXK", unit: "tấn" },
    { src: "consumption", key: "domestic_total", label: "Trong nước", unit: "tấn" },
    { src: "consumption", key: "internal_total", label: "Nội bộ", unit: "tấn" },
    { src: "consumption", key: "revenue_ty", label: "Doanh thu", unit: "tỷ đồng" },
    { src: "consumption", key: "avg_sell_price", label: "Giá bán BQ", unit: "triệu đ/tấn", noSum: true },
  ] },
  { label: "Tồn kho (số thời điểm)", cols: [
    { src: "consumption", key: "stock_as_of", label: "Ngày lấy số tồn", unit: "", date: true, noSum: true },
    { src: "consumption", key: "stock_finished", label: "Tồn kho thành phẩm", unit: "tấn" },
    { src: "consumption", key: "stock_not_warehoused", label: "Chưa nhập kho", unit: "tấn" },
    { src: "consumption", key: "stock_warehoused", label: "Đã nhập kho", unit: "tấn" },
    { src: "consumption", key: "stock_finished_hd", label: "Đã ký HĐ chưa giao", unit: "tấn quy khô" },
    { src: "consumption", key: "stock_material", label: "Tồn nguyên liệu", unit: "tấn" },
  ] },
];
const COLS = GROUPS.flatMap((g) => g.cols);

const num = (v: unknown): number | null => (typeof v === "number" ? v : null);

/** Ô "Ngày lấy số tồn" — tô vàng khi đơn vị đã nhập tới ngày mới hơn mà chưa cập nhật tồn. */
function StockDate({ row }: { row?: PeriodRow }) {
  const day = typeof row?.stock_as_of === "string" ? row.stock_as_of : null;
  if (!day) return <span style={{ color: "var(--muted)" }} title="Trong tuần đơn vị chưa nhập tồn kho.">—</span>;
  const last = typeof row?.last_day === "string" ? row.last_day : null;
  const stale = !!last && day < last;
  return (
    <span style={stale ? { color: "var(--warn)", fontWeight: 600 } : undefined}
          title={stale ? `Đơn vị nhập số liệu tới ${dmy(last)} nhưng số tồn là của ngày ${dmy(day)}.` : undefined}>
      {dmy(day)}
    </span>
  );
}

export default function UnitWeekSnapshotTable({ snap }: { snap: SnapshotDetail }) {
  const byCompany = (src: Src) => new Map(snap[src].rows.map((r) => [r.company, r]));
  const rows = { purchase: byCompany("purchase"), consumption: byCompany("consumption") };
  const companies = snap.consumption.rows.map((r) => ({ name: r.company, region: r.region }));
  const totals: Record<Src, SnapshotTotals> = snap.totals;

  return (
    <div className="card" style={{ padding: 0, overflow: "auto" }}>
      <table>
        <thead>
          <tr>
            <th rowSpan={2} style={{ minWidth: 110 }}>Khu vực</th>
            <th rowSpan={2} style={{ minWidth: 170 }}>Đơn vị</th>
            {GROUPS.map((g) => (
              <th key={g.label} colSpan={g.cols.length} style={{ textAlign: "center" }}>{g.label}</th>
            ))}
          </tr>
          <tr>
            {COLS.map((c) => (
              <th key={c.key + c.src} className="r" style={{ minWidth: 104 }}>
                {c.label}
                <div style={{ fontWeight: 400, fontSize: 10.5, opacity: 0.6 }}>{c.unit}</div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {companies.map(({ name, region }) => {
            const p = rows.purchase.get(name);
            const c = rows.consumption.get(name);
            // Có phiếu ngày, HOẶC có số khác 0 (đơn vị chỉ có đợt giao theo hợp đồng / tồn kho mà
            // không nhập biểu ngày vẫn là có số — không được tô mờ như dòng trống).
            const hasData = (p?.days ?? 0) + (c?.days ?? 0) > 0
              || COLS.some((col) => !col.date && !col.noSum && (num(rows[col.src].get(name)?.[col.key]) ?? 0) !== 0);
            return (
              <tr key={name} style={{ opacity: hasData ? 1 : 0.45 }}>
                <td>{region ?? "—"}</td>
                <td style={{ fontWeight: 500 }}>{name}</td>
                {COLS.map((col) => (
                  <td key={col.key + col.src} className="r">
                    {col.date ? <StockDate row={c} />
                      : fmtNum(num(rows[col.src].get(name)?.[col.key]), displayDigits(col.unit))}
                  </td>
                ))}
              </tr>
            );
          })}
          <tr style={{ fontWeight: 600, background: "rgba(125,125,125,.08)" }}>
            <td />
            <td>Tổng cộng</td>
            {COLS.map((col) => (
              <td key={col.key + col.src} className="r">
                {col.noSum ? "" : fmtNum(num(totals[col.src][col.key]), displayDigits(col.unit))}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
