/* Đầu màn drill-down: đường dẫn lớp (Toàn Tập đoàn › Khu vực › Đơn vị › Ngày) + thẻ KPI tổng
   + biểu đồ cột của lớp đang xem — bấm cột cũng đi sâu như bấm dòng trong bảng. */

import { HomeOutlined } from "@ant-design/icons";
import { Breadcrumb } from "antd";

import { dmy } from "../../../../lib/date";
import type { StatsRow } from "../../../../lib/unit-analytics-client";
import { displayDigits, fmtNum } from "../../../../lib/unit-daily-fields";
import DrillBarChart from "../../charts/DrillBarChart";
import { DIM_LABEL, type DrillDim, type DrillStep } from "./use-drill";

export type Kpi = { key: string; label: string; unit: string };

type Props = {
  steps: DrillStep[];
  onUpTo: (n: number) => void;
  currentDim: DrillDim;
  canDrill: boolean;
  rows: StatsRow[];
  totals: StatsRow | null;
  kpis: Kpi[];
  chartKey: string;          // chỉ tiêu vẽ cột (vd tổng sản lượng)
  chartLabel: string;
  onPick: (value: string) => void;
};

const stepText = (s: DrillStep) => (s.dim === "day" ? dmy(s.value) : s.value);

export default function DrillHeader({
  steps, onUpTo, currentDim, canDrill, rows, totals, kpis, chartKey, chartLabel, onPick,
}: Props) {
  const items = [
    { title: (<span style={{ cursor: "pointer" }}><HomeOutlined /> Toàn Tập đoàn</span>), onClick: () => onUpTo(0) },
    ...steps.map((s, i) => ({
      title: (<span style={{ cursor: i < steps.length - 1 ? "pointer" : "default" }}>
        <span style={{ color: "var(--muted)" }}>{DIM_LABEL[s.dim]}: </span>{stepText(s)}
      </span>),
      onClick: () => onUpTo(i + 1),
    })),
  ];

  // Biểu đồ: 12 nhóm lớn nhất của lớp đang xem (nhiều hơn thì nhìn không ra cột nào với cột nào).
  const top = [...rows]
    .filter((r) => typeof r[chartKey] === "number")
    .sort((a, b) => (b[chartKey] as number) - (a[chartKey] as number))
    .slice(0, 12);

  return (
    <>
      <div className="card" style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <Breadcrumb items={items} />
        <span style={{ color: "var(--muted)", fontSize: 12, marginLeft: "auto" }}>
          Đang xem theo <b>{DIM_LABEL[currentDim]}</b>
          {canDrill && " · bấm vào dòng hoặc cột để xem chi tiết"}
        </span>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
        {kpis.map((k) => (
          <div key={k.key} className="card" style={{ flex: "1 1 170px", minWidth: 170 }}>
            <div style={{ color: "var(--muted)", fontSize: 12 }}>{k.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>
              {fmtNum(typeof totals?.[k.key] === "number" ? (totals[k.key] as number) : null,
                      displayDigits(k.unit))}
            </div>
            <div style={{ color: "var(--muted)", fontSize: 12 }}>{k.unit}</div>
          </div>
        ))}
      </div>

      {top.length > 1 && (
        <div className="card">
          <div className="card-head">
            <div>
              <h3>{chartLabel} theo {DIM_LABEL[currentDim]}</h3>
              <div className="sub">
                {top.length} nhóm lớn nhất{canDrill ? " · bấm vào cột để xem chi tiết" : ""}
              </div>
            </div>
          </div>
          <div style={{ height: 260 }}>
            <DrillBarChart
              labels={top.map((r) => (currentDim === "day" ? dmy(r.key) : r.key))}
              values={top.map((r) => r[chartKey] as number)}
              onPick={canDrill ? (i) => onPick(top[i].key) : undefined}
            />
          </div>
        </div>
      )}
    </>
  );
}
