import type { ChartData, ChartOptions } from "chart.js";
import { Bar } from "react-chartjs-2";

import { AXIS } from "./chart-setup";

/** Cột cho màn Thống kê — bấm vào cột để đi sâu 1 lớp (khu vực → đơn vị → ngày…).
 *  Không truyền `onPick` = biểu đồ chỉ để xem (lớp cuối). */
export default function DrillBarChart(
  { labels, values, onPick, color = "#16AF67" }:
  { labels: string[]; values: number[]; onPick?: (index: number) => void; color?: string },
) {
  const data: ChartData<"bar"> = {
    labels,
    datasets: [{ data: values, backgroundColor: `${color}cc`, hoverBackgroundColor: color, borderRadius: 4 }],
  };

  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    onClick: (_e, els) => { if (onPick && els.length) onPick(els[0].index); },
    onHover: (e, els) => {
      const el = e.native?.target as HTMLElement | undefined;
      if (el) el.style.cursor = onPick && els.length ? "pointer" : "default";
    },
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: AXIS.tick, maxRotation: 45, minRotation: 0 }, grid: { display: false } },
      y: { ticks: { color: AXIS.tick }, grid: { color: AXIS.grid }, beginAtZero: true },
    },
  };

  return <Bar data={data} options={options} />;
}
