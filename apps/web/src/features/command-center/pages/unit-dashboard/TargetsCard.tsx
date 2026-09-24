/* Card "Chỉ tiêu năm" — tiến độ LŨY KẾ từ 01/01 tới ngày cuối kỳ (không so số một tháng với chỉ tiêu
   cả năm). Mỗi chỉ tiêu một thanh, kèm vạch "tiến độ thời gian" để thấy ngay đang nhanh hay chậm.
   % hiện SỐ THẬT kể cả khi vượt 100% (thanh thì đầy ở 100%). */

import { AimOutlined } from "@ant-design/icons";
import { Progress, Tooltip } from "antd";

import { dmy } from "../../../../lib/date";
import type { TargetsBlock } from "../../../../lib/unit-dashboard-client";
import DashboardCard from "./DashboardCard";
import { fmtByUnit, fmtPct, isBehind, withUnit } from "./dashboard-format";
import TargetsBreakdownTable from "./TargetsBreakdownTable";
import type { BlockState } from "./use-dashboard-block";

type Item = TargetsBlock["items"][number];

function TargetRow({ item, timePct }: { item: Item; timePct: number }) {
  const behind = isBehind(item.pct, timePct);
  return (
    <div className="ud-target">
      <div className="ud-target-head">
        <b>{item.label}</b>
        <span className="ud-target-nums">
          {item.plan == null ? withUnit(fmtByUnit(item.done, item.unit), item.unit)
            : `${fmtByUnit(item.done, item.unit)} / ${fmtByUnit(item.plan, item.unit)} ${item.unit}`}
        </span>
      </div>
      {item.plan == null ? (
        <div className="ud-muted ud-small">Chưa giao chỉ tiêu</div>
      ) : item.pct == null ? (
        <div className="ud-muted ud-small">{item.note || "Chưa tính được % hoàn thành."}</div>
      ) : (
        <div className="ud-target-body">
          <div className="ud-target-bar">
            <Progress percent={Math.min(Math.max(item.pct, 0), 100)} showInfo={false} status="normal"
                      strokeColor={behind ? "var(--warn)" : "var(--accent)"} />
            <Tooltip title={`Tiến độ thời gian: ${fmtPct(timePct)} của năm đã qua`}>
              <span className="ud-time-mark" style={{ left: `${Math.min(timePct, 100)}%` }} />
            </Tooltip>
          </div>
          <span className={`ud-target-pct${behind ? " ud-warn" : ""}`}>{fmtPct(item.pct)}</span>
        </div>
      )}
      {item.plan != null && item.pct != null && item.note && (
        <div className="ud-muted ud-small">{item.note}</div>
      )}
    </div>
  );
}

export default function TargetsCard({ state }: { state: BlockState<TargetsBlock> }) {
  const d = state.data;
  return (
    <DashboardCard
      id="ud-targets" state={state} warnings={(t) => t.warnings}
      title={<><AimOutlined style={{ marginRight: 6 }} />Chỉ tiêu năm {d?.year ?? ""}</>}
      sub={d && <>Lũy kế {dmy(d.date_from)} → {dmy(d.date_to)} · vạch dọc = tiến độ thời gian
        ({fmtPct(d.time_pct)} của năm đã qua) để so nhanh hay chậm.</>}
    >
      {(t) => (
        <>
          <div className="ud-target-grid">
            {t.items.map((it) => <TargetRow key={it.key} item={it} timePct={t.time_pct} />)}
          </div>
          {t.breakdown.length > 0 && (
            <TargetsBreakdownTable
              rows={t.breakdown} timePct={t.time_pct}
              childLabel={t.scope.child_label ?? "Phạm vi con"}
            />
          )}
        </>
      )}
    </DashboardCard>
  );
}
