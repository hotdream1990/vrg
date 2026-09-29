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

/** Liệt kê tối đa ngần này đơn vị dùng số cũ — dài hơn thì gộp phần đuôi. */
const MAX_STALE_LISTED = 4;

/** Ghi chú SỐ CŨ: đơn vị tick "không phát sinh tồn kho" thì giữ số lần khai gần nhất — người xem phải
 *  biết số đó khai ngày nào, cũ bao nhiêu ngày (như cột "Số cũ" ở màn Thống kê tồn kho). */
function staleNote(d: StockBlock): string | null {
  const { dates, age_days: age } = d.totals;
  if (!age) return null;
  if (d.scope.scope === "unit") {
    return `Số cũ ${age} ngày: đơn vị tick “không phát sinh tồn kho”, số lấy từ lần khai ngày ${dmy(dates[0])}.`;
  }
  const stale = d.coverage?.stale ?? [];
  if (!stale.length) return `Có số lấy từ ngày ${dates.map(dmy).join(", ")} — số cũ nhất ${age} ngày.`;
  const shown = stale.slice(0, MAX_STALE_LISTED)
    .map((s) => `${s.company} (khai ${dmy(s.as_of)}, cũ ${s.age_days} ngày)`).join(" · ");
  const more = stale.length > MAX_STALE_LISTED ? ` …và ${stale.length - MAX_STALE_LISTED} đơn vị khác` : "";
  return `${stale.length} đơn vị dùng số cũ (tick “không phát sinh tồn kho” → giữ số lần khai gần nhất): `
    + `${shown}${more}.`;
}

function StockBody({ d, onPickAsOf }: { d: StockBlock; onPickAsOf: Props["onPickAsOf"] }) {
  const hint = d.latest_stock_day;
  const note = staleNote(d);
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
      {d.auto_as_of && (
        <p className="ud-note">
          {d.scope.scope === "unit"
            ? "Ngày chốt tự lấy: ngày khai tồn kho gần nhất của đơn vị."
            : "Ngày chốt tự lấy: ngày gần nhất đã đủ đơn vị khai — trùng ngày cuối của biểu đồ diễn biến "
              + "tồn kho (đơn vị được nhập tới 11:00 hôm sau nên hôm nay thường chưa đủ số)."}
          {" "}Chọn ngày khác ở ô “Chốt tồn kho”.
        </p>
      )}
      {note && <p className="ud-note ud-warn">{note}</p>}
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
                ...(r.age_days ? [r.as_of ? `Số khai ngày ${dmy(r.as_of)} — cũ ${r.age_days} ngày`
                                          : `Có số cũ tới ${r.age_days} ngày`] : []),
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
