/* Card "Chỉ tiêu năm" — tiến độ LŨY KẾ từ 01/01 tới ngày cuối kỳ (không so số một tháng với chỉ tiêu
   cả năm). Mỗi chỉ tiêu một thanh, kèm vạch "tiến độ thời gian" để thấy ngay đang nhanh hay chậm.
   % hiện SỐ THẬT kể cả khi vượt 100% (thanh thì đầy ở 100%).
   Số của mỗi chỉ tiêu tính trên RỔ đơn vị được giao KH (khác thẻ KPI = cả phạm vi) — luôn ghi rõ rổ. */

import { AimOutlined } from "@ant-design/icons";
import { Progress, Tooltip } from "antd";

import { dmy } from "../../../../lib/date";
import type { TargetsBlock } from "../../../../lib/unit-dashboard-client";
import DashboardCard from "./DashboardCard";
import { differsNotably, fmtByUnit, fmtPct, isBehind, withUnit } from "./dashboard-format";
import TargetsBreakdownTable from "./TargetsBreakdownTable";
import type { BlockState } from "./use-dashboard-block";

type Item = TargetsBlock["items"][number];

function TargetRow({ item, timePct, single }: { item: Item; timePct: number; single: boolean }) {
  const behind = isBehind(item.pct, timePct);
  const u = item.unit;
  return (
    <div className="ud-target">
      <div className="ud-target-head">
        <b>{item.label}</b>
        <span className="ud-target-nums">
          {item.plan == null ? withUnit(fmtByUnit(item.done, u), u)
            : `${fmtByUnit(item.done, u)} / ${fmtByUnit(item.plan, u)} ${u}`
              // Nêu RỔ tính %: chỉ các đơn vị được giao KH — xem 1 đơn vị thì khỏi ghi.
              + (single ? "" : ` · ${item.units_planned.toLocaleString("vi-VN")} đơn vị có KH`)}
        </span>
      </div>
      {item.plan == null ? (
        <div className="ud-muted ud-small">Chưa giao chỉ tiêu</div>
      ) : item.pct == null ? (
        // Có KH mà không ra % = vướng DỮ LIỆU (thiếu tỷ giá, nghi sai đơn vị tính…) → tô cảnh báo.
        <div className="ud-warn ud-small">{item.note || "Chưa tính được % hoàn thành."}</div>
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
      {differsNotably(item.done, item.scope_done) && (
        <div className="ud-muted ud-small">
          Cả phạm vi: {withUnit(fmtByUnit(item.scope_done, u), u)} (gồm đơn vị chưa giao KH)
        </div>
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
            {t.items.map((it) => (
              <TargetRow key={it.key} item={it} timePct={t.time_pct} single={t.scope.scope === "unit"} />
            ))}
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
