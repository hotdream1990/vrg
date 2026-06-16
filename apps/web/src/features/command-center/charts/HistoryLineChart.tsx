import type { ChartData, ChartOptions } from "chart.js";
import { Line } from "react-chartjs-2";

import { AXIS } from "./chart-setup";

type Point = { as_of: string; price: number };

/** Biểu đồ lịch sử THẬT (từ DB /history). Trục x rút gọn ngày, fill nhẹ dưới đường. */
export default function HistoryLineChart({ points, label, color = "#22c55e" }: { points: Point[]; label: string; color?: string }) {
  const data: ChartData<"line"> = {
    labels: points.map((p) => p.as_of.slice(5)), // MM-DD
    datasets: [
      {
        label,
        data: points.map((p) => p.price),
        borderColor: color,
        backgroundColor: `${color}22`,
        tension: 0.25,
        fill: true,
        pointRadius: 0,
        borderWidth: 2,
      },
    ],
  };

  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { color: AXIS.legend, boxWidth: 14, font: { size: 11 } } } },
    scales: {
      x: { ticks: { color: AXIS.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }, grid: { color: AXIS.grid } },
      y: { ticks: { color: AXIS.tick }, grid: { color: AXIS.grid } },
    },
  };

  return <Line data={data} options={options} />;
}
