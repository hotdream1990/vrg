/* Bảng "Tiến độ bán hàng theo khu vực / đơn vị" dưới card Tiến độ bán hàng năm. 3 nhóm cột: HĐ dài
   hạn (HĐDH) · Sản lượng cả năm so KH bán hàng · Doanh thu dự kiến so KH. Ô KH bán hàng ghi tổng
   kèm dòng nhỏ tách khai thác / thu mua. Giữ thứ tự dòng server trả — không tự sắp lại.
   Bảng rộng → cuộn ngang TRONG `.ud-table-wrap` trên màn hẹp, không kéo cả trang. */

import type { ReactNode } from "react";

import type { OutlookBreakdownRow } from "../../../../lib/unit-dashboard-client";
import { type Num, differsNotably, fmtTon, fmtTy } from "./dashboard-format";
import { MiniPct } from "./OutlookBars";

type Col = { label: string; title: string; cell: (r: OutlookBreakdownRow) => ReactNode };
type Group = { label: string; cols: Col[] };

/** Ô KH bán hàng: tổng + "KT … · TM …" (KT "—" = đơn vị chưa nhập KH khai thác, ngoài rổ %). */
function PlanCell({ r }: { r: OutlookBreakdownRow }) {
  if (r.plan_total == null && r.plan_exploit == null && r.plan_purchase == null) return <>—</>;
  return (
    <>
      <div>{fmtTon(r.plan_total)}</div>
      <div className="ud-cell-sub">KT {fmtTon(r.plan_exploit)} · TM {fmtTon(r.plan_purchase)}</div>
    </>
  );
}

/** Tử số của % phải cùng RỔ với mẫu số: dòng có KH thì hiện số của rổ (đơn vị có KH), kèm dòng nhỏ
 *  "cả nhóm …" khi số của cả nhóm khác đáng kể — đặt số cả nhóm cạnh % của rổ là đúng kiểu "lệch
 *  logic" khách phản ánh 26/09/2026. Dòng chưa có KH thì chỉ có số cả nhóm. */
function BasketCell({ basket, whole, fmt }: { basket?: Num; whole: Num; fmt: (v: Num) => string }) {
  if (basket == null) return <>{fmt(whole)}</>;
  return (
    <>
      <div>{fmt(basket)}</div>
      {differsNotably(basket, whole) && <div className="ud-cell-sub">cả nhóm {fmt(whole)}</div>}
    </>
  );
}

const GROUPS: Group[] = [
  { label: "HĐ dài hạn (HĐDH)", cols: [
    { label: "Còn lại (tấn)", title: "Cam kết HĐDH còn phải giao (HĐDH còn hiệu lực)",
      cell: (r) => fmtTon(r.lt_remaining) },
    { label: "% thực hiện", title: "Đã giao / cam kết của các HĐDH",
      cell: (r) => <MiniPct pct={r.lt_pct} /> },
  ] },
  { label: "Sản lượng cả năm (tấn)", cols: [
    { label: "Còn phải giao", title: "HĐ chuyến đã ký chưa giao + HĐ dài hạn còn phải giao (+ HĐ chưa khai loại)",
      cell: (r) => fmtTon(r.to_deliver) },
    { label: "Bán cả năm", title: "Dự kiến = đã giao lũy kế + còn phải giao; dòng có KH ghi số của các đơn vị có KH (tử số của % KH)",
      cell: (r) => <BasketCell basket={r.qty_basket_projected} whole={r.projected} fmt={fmtTon} /> },
    { label: "KH (KT + TM)", title: "KH bán hàng = KH khai thác (KT) + KH thu mua (TM)",
      cell: (r) => <PlanCell r={r} /> },
    { label: "% KH", title: "Bán cả năm (dự kiến) / KH bán hàng",
      cell: (r) => <MiniPct pct={r.qty_pct} /> },
  ] },
  { label: "Doanh thu (tỷ đồng)", cols: [
    { label: "Dự kiến", title: "DT đã thực hiện + SL còn phải giao × giá bán BQ lũy kế của đơn vị; dòng có KH ghi số của các đơn vị có KH",
      cell: (r) => <BasketCell basket={r.revenue_basket_projected} whole={r.revenue_projected} fmt={fmtTy} /> },
    { label: "KH", title: "Kế hoạch doanh thu năm", cell: (r) => fmtTy(r.plan_revenue) },
    { label: "% KH", title: "Doanh thu dự kiến / KH doanh thu",
      cell: (r) => <MiniPct pct={r.revenue_pct} /> },
  ] },
];

type Props = { rows: OutlookBreakdownRow[]; childLabel: string };

export default function OutlookBreakdownTable({ rows, childLabel }: Props) {
  return (
    <div className="ud-table-wrap">
      <div className="ud-mini-title">
        Tiến độ bán hàng theo {childLabel.toLowerCase()}
        <span className="ud-muted"> · rê chuột lên tiêu đề cột để xem cách tính · “—” là chưa có số</span>
      </div>
      <table className="ud-table ud-ol-table">
        <thead>
          <tr>
            <th rowSpan={2}>{childLabel}</th>
            {GROUPS.map((g) => (
              <th key={g.label} colSpan={g.cols.length} className="ud-th-group ud-col-start">{g.label}</th>
            ))}
          </tr>
          <tr>
            {GROUPS.flatMap((g) => g.cols.map((c, i) => (
              <th key={`${g.label}-${c.label}`} title={c.title}
                  className={`r${i === 0 ? " ud-col-start" : ""}`}>{c.label}</th>
            )))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <td>{r.label}</td>
              {GROUPS.flatMap((g) => g.cols.map((c, i) => (
                <td key={`${g.label}-${c.label}`} className={`r${i === 0 ? " ud-col-start" : ""}`}>
                  {c.cell(r)}
                </td>
              )))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
