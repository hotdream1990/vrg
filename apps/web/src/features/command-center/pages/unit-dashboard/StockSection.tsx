/* Section "Tồn kho" (ảnh chụp tại NGÀY CHỐT): 6 chỉ số, độ phủ đơn vị, gợi ý ngày gần nhất có số,
   tồn thành phẩm theo chủng loại và (phạm vi Tập đoàn/khu vực) theo khu vực/đơn vị.
   Tồn kho là số THỜI ĐIỂM — không mượn số ngày khác đắp sang; thiếu thì để trống + gợi ý ngày. */

import { DatabaseOutlined } from "@ant-design/icons";
import { Alert, Button } from "antd";

import { dmy } from "../../../../lib/date";
import type { StockBlock } from "../../../../lib/unit-dashboard-client";
import StockCoverageBar from "../analytics/StockCoverageBar";
import DashboardCard from "./DashboardCard";
import { fmtTon, sortDesc, withUnit } from "./dashboard-format";
import HBarChart from "./HBarChart";
import StockStats from "./StockStats";
import type { BlockState } from "./use-dashboard-block";

type Props = {
  state: BlockState<StockBlock>;
  onPickAsOf: (iso: string) => void;
};

/** Ghi chú ngày lấy số khi ảnh chụp gom từ ngày khác ngày chốt (đơn vị tick "không phát sinh tồn
 *  kho" thì giữ số lần khai gần nhất) — người xem phải biết số không cùng một ngày. */
function datesNote(d: StockBlock): string | null {
  const { dates, age_days: age } = d.totals;
  const other = dates.filter((x) => x !== d.as_of);
  if (!other.length) return null;
  const list = dates.length > 4 ? `${dates.slice(0, 4).map(dmy).join(", ")}…` : dates.map(dmy).join(", ");
  return `Số lấy từ ngày ${list}${age ? ` — số cũ nhất cách ngày chốt ${age} ngày` : ""}.`;
}

function StockBody({ d, onPickAsOf }: { d: StockBlock; onPickAsOf: Props["onPickAsOf"] }) {
  const hint = d.latest_stock_day;
  const note = datesNote(d);
  const breakdown = sortDesc(d.breakdown, (r) => r.total);
  // Đơn vị/khu vực đã ký nhiều hơn lượng đang có — nêu tên ngay, đừng để nằm trong tooltip.
  const short = d.breakdown.filter((r) => r.tradable != null && r.tradable < 0);
  const grades = (
    <HBarChart
      title="Tồn thành phẩm theo chủng loại (tấn)" unit="tấn" format={fmtTon} color="#22c55e"
      labels={d.by_grade.map((g) => g.grade)} values={d.by_grade.map((g) => g.qty)}
      empty="Chưa có số tồn theo chủng loại tại ngày chốt."
    />
  );
  return (
    <>
      {hint && (
        <Alert
          type="info" showIcon className="ud-alert"
          title={`Chưa có số tồn kho ngày ${dmy(d.as_of)}. Ngày gần nhất có số là ${dmy(hint)}.`}
          action={<Button type="link" size="small" onClick={() => onPickAsOf(hint)}>Xem ngày {dmy(hint)}</Button>}
        />
      )}
      <StockStats totals={d.totals} />
      {note && <p className="ud-note">{note}</p>}
      {d.scope.scope !== "unit" && d.coverage && <StockCoverageBar asOf={d.as_of} coverage={d.coverage} />}
      {short.length > 0 && (
        <p className="ud-note ud-neg">
          Đã ký nhiều hơn tồn đang có (thiếu hàng để giao):{" "}
          {short.map((r) => `${r.label} ${withUnit(fmtTon(r.tradable), "tấn")}`).join(" · ")}.
        </p>
      )}
      {breakdown.length === 0 ? grades : (
        <div className="ud-split ud-split-even">
          {grades}
          <HBarChart
            title={`Tồn thành phẩm theo ${(d.scope.child_label ?? "phạm vi con").toLowerCase()} (tấn)`}
            unit="tấn" format={fmtTon} color="#38bdf8"
            labels={breakdown.map((r) => r.label)} values={breakdown.map((r) => r.total)}
            notes={(i) => {
              const r = breakdown[i];
              return [
                `Đã ký HĐ chưa giao: ${withUnit(fmtTon(r.signed_undelivered), "tấn")}`,
                `Có thể giao dịch: ${withUnit(fmtTon(r.tradable), "tấn")}`,
                `Tồn nguyên liệu: ${withUnit(fmtTon(r.material), "tấn quy khô")}`,
                ...(r.as_of && r.as_of !== d.as_of ? [`Số lấy ngày ${dmy(r.as_of)}`] : []),
              ];
            }}
          />
        </div>
      )}
    </>
  );
}

export default function StockSection({ state, onPickAsOf }: Props) {
  const d = state.data;
  return (
    <DashboardCard
      id="ud-stock" state={state} warnings={(s) => s.warnings}
      title={<><DatabaseOutlined style={{ marginRight: 6 }} />Tồn kho{d ? ` tại ${dmy(d.as_of)}` : ""}</>}
      sub="Số thời điểm tại ngày chốt (không cộng dồn theo kỳ) · tấn"
    >
      {(s) => <StockBody d={s} onPickAsOf={onPickAsOf} />}
    </DashboardCard>
  );
}
