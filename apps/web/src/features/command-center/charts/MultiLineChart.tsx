import type { ChartData, ChartOptions } from "chart.js";
import { Line } from "react-chartjs-2";

import { AXIS } from "./chart-setup";

type Series = { name: string; values: (number | null)[]; color?: string };
const PALETTE = ["#16AF67", "#2563eb", "#a855f7", "#f59e0b", "#ef4444", "#0891b2"];

/** Biểu đồ nhiều đường (labels chung). Dùng cho tỷ giá base-100 / chuỗi chuẩn hoá. */
export default function MultiLineChart({ labels, series }: { labels: string[]; series: Series[] }) {
  const data: ChartData<"line"> = {
    labels,
    datasets: series.map((s, i) => ({
      label: s.name,
      data: s.values,
      borderColor: s.color ?? PALETTE[i % PALETTE.length],
      backgroundColor: "transparent",
      tension: 0.25,
      pointRadius: 0,
      borderWidth: 2,
      spanGaps: true,
    })),
  };
  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: { legend: { labels: { color: AXIS.legend, boxWidth: 12, font: { size: 10 } } } },
    scales: {
      x: { ticks: { color: AXIS.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { color: AXIS.grid } },
      y: { ticks: { color: AXIS.tick }, grid: { color: AXIS.grid } },
    },
  };
  return <Line data={data} options={options} />;
}
