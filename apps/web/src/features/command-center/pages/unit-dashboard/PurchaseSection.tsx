/* Section "Thu mua": diễn biến sản lượng theo loại mủ + giá mủ nước BQ, bảng theo LOẠI MỦ, thành phẩm
   mua ngoài theo chủng loại, và (phạm vi Tập đoàn/khu vực) cơ cấu theo khu vực/đơn vị.
   Mủ nước/chén/dây KHÔNG chia chủng loại (luật 22/09/2026) — chỉ thành phẩm có chủng loại. */

import { ShoppingCartOutlined } from "@ant-design/icons";

import { dmy } from "../../../../lib/date";
import type { PurchaseBlock } from "../../../../lib/unit-dashboard-client";
import DashboardCard from "./DashboardCard";
import { bucketLabel, fmtNum, fmtPrice, fmtTon, priceDigits, sortDesc, withUnit } from "./dashboard-format";
import HBarChart from "./HBarChart";
import TrendBarChart from "./TrendBarChart";
import type { BlockState } from "./use-dashboard-block";

const COLORS = { latex: "#38bdf8", cup: "#f59e0b", lace: "#a855f7", finished: "#22c55e" };

function MaterialTable({ d }: { d: PurchaseBlock }) {
  const t = d.totals, u = d.price_units;
  const rows = [
    { name: "Mủ nước", qty: t.qty_latex, price: t.price_latex_avg, unit: u.latex },
    { name: "Mủ chén", qty: t.qty_cup, price: t.price_cup_avg, unit: u.cup },
    { name: "Mủ dây", qty: t.qty_lace, price: t.price_lace_avg, unit: u.lace },
    { name: "Thành phẩm mua ngoài", qty: t.qty_finished, price: t.price_finished_avg, unit: u.finished },
  ];
  return (
    <table className="ud-table">
      <thead>
        <tr><th>Loại mủ</th><th className="r">SL (tấn)</th><th className="r">Giá BQ</th><th>Đơn vị giá</th></tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.name}>
            <td>{r.name}</td>
            <td className="r">{fmtTon(r.qty)}</td>
            <td className="r">{fmtPrice(r.price, r.unit)}</td>
            <td className="ud-muted">{r.unit}</td>
          </tr>
        ))}
        <tr className="ud-total">
          <td>Cộng mủ nguyên liệu</td><td className="r">{fmtTon(t.qty_material)}</td><td /><td />
        </tr>
        <tr className="ud-total">
          <td>Tổng (gồm thành phẩm)</td><td className="r">{fmtTon(t.qty_total)}</td><td /><td />
        </tr>
      </tbody>
    </table>
  );
}

function PurchaseBody({ d }: { d: PurchaseBlock }) {
  const labels = d.trend.map((r) => bucketLabel(r.as_of));
  const grades = d.finished_by_grade;
  const pu = d.price_units;
  const child = d.scope.child_label;
  const breakdown = sortDesc(d.breakdown, (r) => r.qty_material);
  return (
    <>
      <div className="ud-split">
        <div>
          {d.trend.length === 0 ? (
            <div className="scan-empty">Chưa có số thu mua trong kỳ.</div>
          ) : (
            <div className="chart-wrap">
              <TrendBarChart
                labels={labels}
                series={[
                  { label: "Mủ nước", data: d.trend.map((r) => r.qty_latex), color: COLORS.latex },
                  { label: "Mủ chén", data: d.trend.map((r) => r.qty_cup), color: COLORS.cup },
                  { label: "Mủ dây", data: d.trend.map((r) => r.qty_lace), color: COLORS.lace },
                  { label: "Thành phẩm", data: d.trend.map((r) => r.qty_finished), color: COLORS.finished },
                ]}
                line={{ label: "Giá mủ nước BQ", data: d.trend.map((r) => r.price_latex_avg),
                        unit: d.price_units.latex, color: "#0f172a",
                        digits: priceDigits(d.price_units.latex) }}
              />
            </div>
          )}
          <p className="ud-note">
            {fmtNum(d.totals.days)} ngày có số liệu · {fmtNum(d.totals.no_purchase_days)} ngày khai
            “không thu mua”. Mủ nước/chén/dây không chia chủng loại — chỉ thành phẩm mua ngoài có chủng loại.
          </p>
        </div>
        <div>
          <MaterialTable d={d} />
          <HBarChart
            title="Thu mua thành phẩm theo chủng loại" unit="tấn" format={fmtTon} color={COLORS.finished}
            labels={grades.map((g) => g.grade)} values={grades.map((g) => g.qty)}
            notes={(i) => [`Giá BQ: ${withUnit(fmtPrice(grades[i].price_avg, pu.finished), pu.finished)}`]}
            empty="Kỳ này không mua thành phẩm."
          />
        </div>
      </div>
      {breakdown.length > 0 && (
        <HBarChart
          title={`Mủ nguyên liệu theo ${(child ?? "phạm vi con").toLowerCase()} (tấn)`} unit="tấn"
          format={fmtTon} color={COLORS.latex}
          labels={breakdown.map((r) => r.label)} values={breakdown.map((r) => r.qty_material)}
          notes={(i) => [
            `Thành phẩm: ${withUnit(fmtTon(breakdown[i].qty_finished), "tấn")}`,
            `Giá mủ nước BQ: ${withUnit(fmtPrice(breakdown[i].price_latex_avg, pu.latex), pu.latex)}`,
          ]}
        />
      )}
    </>
  );
}

export default function PurchaseSection({ state }: { state: BlockState<PurchaseBlock> }) {
  const d = state.data;
  return (
    <DashboardCard
      id="ud-purchase" state={state} warnings={(p) => p.warnings}
      title={<><ShoppingCartOutlined style={{ marginRight: 6 }} />Thu mua</>}
      sub={d && `${dmy(d.date_from)} → ${dmy(d.date_to)} · mỗi cột = 1 ${d.bucket === "month" ? "tháng" : "ngày"} · tấn`}
    >
      {(p) => <PurchaseBody d={p} />}
    </DashboardCard>
  );
}
