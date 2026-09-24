/* Diễn biến tồn kho theo NGÀY của phạm vi đang xem (tối đa 180 ngày, kết thúc ở min(đến ngày, hôm
   nay)). Đổi cách xem chỉ tải lại khối này — các khối khác giữ nguyên. Tách card riêng khỏi ảnh chụp
   tồn kho vì hai khối tải độc lập: khối này lỗi không che mất số tồn tại ngày chốt. */

import { LineChartOutlined } from "@ant-design/icons";
import { Segmented } from "antd";

import { dmy } from "../../../../lib/date";
import type { DashStockSeries, DashStockView } from "../../../../lib/unit-dashboard-client";
import StackedDaysChart from "../../charts/StackedDaysChart";
import DashboardCard from "./DashboardCard";
import { fmtTon, withUnit } from "./dashboard-format";
import type { BlockState } from "./use-dashboard-block";

const VIEWS: { value: DashStockView; label: string; sub: string }[] = [
  { value: "warehouse", label: "Đã / chưa nhập kho",
    sub: "Mỗi cột = tồn thành phẩm = đã nhập kho + chưa nhập kho" },
  { value: "grade", label: "Chủng loại", sub: "Mỗi cột = tồn thành phẩm chia theo chủng loại" },
  { value: "structure", label: "Cơ cấu hợp đồng",
    sub: "Mỗi cột = đã ký hợp đồng (chưa giao) + tồn tự do (chưa ký)" },
  { value: "free_grade", label: "Tự do theo chủng loại",
    sub: "Mỗi cột = phần CÒN BÁN ĐƯỢC (tồn − đã ký) của từng chủng loại" },
];

/** Liệt kê từng ngày khi ít; nhiều ngày thì gộp thành khoảng — danh sách dài hơn cả biểu đồ. */
const MAX_PENDING_LISTED = 3;

function pendingNote(pending: DashStockSeries["pending"]): string {
  if (pending.length <= MAX_PENDING_LISTED) {
    return `Chưa vẽ ${pending.map((p) => dmy(p.as_of)).join(", ")} vì đang nhập dở `
      + `(mới ${pending.map((p) => p.units_counted).join(", ")} đơn vị).`;
  }
  return `Chưa vẽ ${pending.length} ngày cuối (${dmy(pending[0].as_of)} → `
    + `${dmy(pending[pending.length - 1].as_of)}) vì chưa đủ đơn vị nhập.`;
}

type Props = {
  state: BlockState<DashStockSeries>;
  view: DashStockView;
  onViewChange: (v: DashStockView) => void;
};

function SeriesBody({ d }: { d: DashStockSeries }) {
  const hasData = d.rows.some((r) => r.total != null);
  const isUnit = d.scope.scope === "unit";
  if (!hasData) return <div className="scan-empty">Chưa có số tồn kho theo ngày trong khoảng này.</div>;
  return (
    <>
      <div className="chart-wrap">
        <StackedDaysChart
          rows={d.rows} series={d.series}
          footer={(r) => {
            const total = `Tổng tồn thành phẩm: ${withUnit(fmtTon(r.total), "tấn")}`;
            const counted = (r as DashStockSeries["rows"][number]).units_counted;
            return isUnit ? total : `${total} · ${counted} đơn vị có tồn`;
          }}
        />
      </div>
      <p className="ud-note">
        {dmy(d.date_from)} → {dmy(d.date_to)}. Mỗi ngày là số thời điểm (không cộng dồn); đơn vị chưa
        khai ngày nào thì ngày đó không có số của đơn vị đó.
        {!isUnit && ` Chuỗi bắt đầu từ ${dmy(d.start_floor)} — trước đó chưa đủ đơn vị nhập để cộng.`}
        {d.pending.length > 0 && ` ${pendingNote(d.pending)}`}
      </p>
    </>
  );
}

export default function StockSeriesCard({ state, view, onViewChange }: Props) {
  const current = VIEWS.find((v) => v.value === view) ?? VIEWS[0];
  return (
    <DashboardCard
      id="ud-stock-series" state={state}
      title={<><LineChartOutlined style={{ marginRight: 6 }} />Diễn biến tồn kho · {current.label}</>}
      sub={`${current.sub} — tấn, theo ngày`}
      extra={
        <Segmented size="small" value={view} onChange={(v) => onViewChange(v as DashStockView)}
                   options={VIEWS.map(({ value, label }) => ({ value, label }))} />
      }
    >
      {(d) => <SeriesBody d={d} />}
    </DashboardCard>
  );
}
