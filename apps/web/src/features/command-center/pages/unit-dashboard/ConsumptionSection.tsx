/* Section "Tiêu thụ": diễn biến sản lượng bán (chia theo LOẠI HỢP ĐỒNG hoặc HÌNH THỨC tiêu thụ) +
   đường doanh thu, bảng theo chủng loại, và (phạm vi Tập đoàn/khu vực) cơ cấu theo khu vực/đơn vị.
   Dòng bán ngoại tệ thiếu tỷ giá KHÔNG được quy đổi → doanh thu/giá BQ thiếu phần đó (có cảnh báo). */

import { ShopOutlined } from "@ant-design/icons";
import { Segmented } from "antd";
import { useState } from "react";

import { dmy } from "../../../../lib/date";
import type { ConsumptionBlock, ConsumptionQtys } from "../../../../lib/unit-dashboard-client";
import ConsumptionGradeTable from "./ConsumptionGradeTable";
import DashboardCard from "./DashboardCard";
import { bucketLabel, fmtPrice, fmtTon, fmtTy, sortDesc, withUnit } from "./dashboard-format";
import HBarChart from "./HBarChart";
import TrendBarChart from "./TrendBarChart";
import type { BlockState } from "./use-dashboard-block";

type Split = "contract" | "channel";
type QtyKey = keyof Omit<ConsumptionQtys, "qty">;

const SPLITS: Record<Split, { label: string; parts: { key: QtyKey; label: string; color: string }[] }> = {
  contract: {
    label: "Loại hợp đồng",
    parts: [
      { key: "qty_long_term", label: "Dài hạn", color: "#22c55e" },
      { key: "qty_principle", label: "HĐ nguyên tắc", color: "#a78bfa" },
      { key: "qty_spot", label: "Chuyến", color: "#38bdf8" },
      { key: "qty_unknown_type", label: "Chưa khai loại HĐ", color: "#94a3b8" },
    ],
  },
  channel: {
    label: "Hình thức",
    parts: [
      { key: "qty_export", label: "XK / UTXK", color: "#6366f1" },
      { key: "qty_domestic", label: "Trong nước", color: "#f59e0b" },
      { key: "qty_internal", label: "Nội bộ", color: "#14b8a6" },
    ],
  },
};

const PRICE_UNIT = "triệu đ/tấn";

function ConsumptionBody({ d, split }: { d: ConsumptionBlock; split: Split }) {
  const parts = SPLITS[split].parts;
  const breakdown = sortDesc(d.breakdown, (r) => r.qty);
  // Dòng thiếu tỷ giá: server đã đưa vào `warnings` (cùng câu với màn Thống kê) → không lặp ở đây.
  return (
    <>
      <div className="ud-split ud-split-even">
        <div>
          {d.trend.length === 0 ? (
            <div className="scan-empty">Chưa có số tiêu thụ trong kỳ.</div>
          ) : (
            <div className="chart-wrap">
              <TrendBarChart
                labels={d.trend.map((r) => bucketLabel(r.as_of))}
                series={parts.map((p) => ({ label: p.label, color: p.color, data: d.trend.map((r) => r[p.key]) }))}
                line={{ label: "Doanh thu", data: d.trend.map((r) => r.revenue_ty), unit: "tỷ đồng",
                        color: "#0f172a", digits: 2, zero: true }}
              />
            </div>
          )}
          <p className="ud-note">
            Tổng kỳ: {parts.map((p) => `${p.label} ${withUnit(fmtTon(d.totals[p.key]), "tấn")}`).join(" · ")}.
            {" "}Doanh thu {withUnit(fmtTy(d.totals.revenue_ty), "tỷ đồng")} · giá bán BQ{" "}
            {withUnit(fmtPrice(d.totals.avg_price_trieu, PRICE_UNIT), PRICE_UNIT)}.
          </p>
        </div>
        <ConsumptionGradeTable rows={d.by_grade} totalQty={d.totals.qty} />
      </div>
      {breakdown.length > 0 && (
        <HBarChart
          title={`Tiêu thụ theo ${(d.scope.child_label ?? "phạm vi con").toLowerCase()} (tấn)`}
          unit="tấn" format={fmtTon} color="#38bdf8"
          labels={breakdown.map((r) => r.label)} values={breakdown.map((r) => r.qty)}
          notes={(i) => [
            `Doanh thu: ${withUnit(fmtTy(breakdown[i].revenue_ty), "tỷ đồng")}`,
            `Giá bán BQ: ${withUnit(fmtPrice(breakdown[i].avg_price_trieu, PRICE_UNIT), PRICE_UNIT)}`,
          ]}
        />
      )}
    </>
  );
}

export default function ConsumptionSection({ state }: { state: BlockState<ConsumptionBlock> }) {
  const [split, setSplit] = useState<Split>("contract");
  const d = state.data;
  return (
    <DashboardCard
      id="ud-consumption" state={state} warnings={(c) => c.warnings}
      title={<><ShopOutlined style={{ marginRight: 6 }} />Tiêu thụ</>}
      sub={d && `${dmy(d.date_from)} → ${dmy(d.date_to)} · mỗi cột = 1 ${d.bucket === "month" ? "tháng" : "ngày"} · tấn`}
      extra={
        <Segmented size="small" value={split} onChange={(v) => setSplit(v as Split)}
                   options={(Object.keys(SPLITS) as Split[]).map((k) => ({ value: k, label: SPLITS[k].label }))} />
      }
    >
      {(c) => <ConsumptionBody d={c} split={split} />}
    </DashboardCard>
  );
}
