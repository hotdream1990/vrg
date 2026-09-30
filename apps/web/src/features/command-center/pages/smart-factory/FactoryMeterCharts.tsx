/* Mỗi chỉ số một biểu đồ cột tiêu thụ theo ngày. Ngày hôm nay (cờ in_progress) tô NHẠT — số chỉ
   tính đến hiện tại; ngày chưa có số (used = null) để TRỐNG cột, không vẽ thành 0. */

import type { ChartData, ChartOptions } from "chart.js";
import { Bar } from "react-chartjs-2";

import { dm } from "../../../../lib/date";
import type { DailyMeters, MetricMeta } from "../../../../lib/smart-factory-client";
import { AXIS } from "../../charts/chart-setup";
import {
  flagText, fmtUsed, METRIC_COLOR, upperFirst, usedWord, withUnit,
} from "./smart-factory-format";

const SOLID = "cc";   // alpha hex: cột bình thường
const FAINT = "55";   // alpha hex: hôm nay (đang chạy)

function DailyUsedChart({ meta, data }: { meta: MetricMeta; data: DailyMeters }) {
  const color = METRIC_COLOR[meta.key] ?? "#16AF67";
  const cells = data.rows.map((r) => r[meta.key]);
  const chartData: ChartData<"bar"> = {
    labels: data.rows.map((r) => dm(r.date)),
    datasets: [{
      label: `${usedWord(meta.key)} (${meta.unit})`,
      data: cells.map((c) => c?.used ?? null),
      backgroundColor: cells.map((c) => `${color}${c?.flag === "in_progress" ? FAINT : SOLID}`),
      borderRadius: 3,
    }],
  };
  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => `${upperFirst(usedWord(meta.key))}: ${withUnit(fmtUsed(ctx.parsed.y, meta.key), meta.unit)}`,
          afterLabel: (ctx) => flagText(cells[ctx.dataIndex]) ?? "",
        },
      },
    },
    scales: {
      x: { grid: { display: false },
           ticks: { color: AXIS.tick, autoSkip: true, maxTicksLimit: 12, maxRotation: 0 } },
      y: { beginAtZero: true, ticks: { color: AXIS.tick }, grid: { color: AXIS.grid },
           title: { display: true, text: meta.unit, color: AXIS.tick } },
    },
  };
  return (
    <div className="card sf-chart-card">
      <h3>{meta.label} — {usedWord(meta.key)} theo ngày</h3>
      <div className="chart-wrap">
        <Bar data={chartData} options={options} />
      </div>
    </div>
  );
}

/** Lưới 3 cột trên màn rộng (2 → 1 cột trên màn hẹp — theo `.grid-3` dùng chung). */
export default function FactoryMeterCharts({ data }: { data: DailyMeters }) {
  const n = data.metrics.length;
  const cls = n >= 3 ? "grid-3" : n === 2 ? "grid-2" : "";
  return (
    <div className={cls} style={cls ? undefined : { marginBottom: 18 }}>
      {data.metrics.map((m) => <DailyUsedChart key={m.key} meta={m} data={data} />)}
    </div>
  );
}
