import type { ChartData, ChartOptions } from "chart.js";
import { Line } from "react-chartjs-2";

import { AXIS } from "./chart-setup";

/** Dải min–max theo ngày: vùng tô giữa "thấp nhất" và "cao nhất", kèm đường trung bình.
 *  Trục y tự co giãn nên thấy rõ chênh lệch nhỏ (khác biểu đồ cột luôn bắt đầu từ 0). */
export default function MinMaxBandChart(
  { labels, min, max, avg, color = "#16AF67", unit = "" }:
  { labels: string[]; min: number[]; max: number[]; avg?: number[]; color?: string; unit?: string },
) {
  const pointRadius = labels.length <= 20 ? 3 : 0;
  const suffix = unit ? ` (${unit})` : "";
  const datasets: ChartData<"line">["datasets"] = [
    { label: `Thấp nhất${suffix}`, data: min, borderColor: `${color}99`, backgroundColor: "transparent",
      borderWidth: 1.5, pointRadius, pointHoverRadius: pointRadius + 2, tension: 0.25 },
    { label: "Cao nhất", data: max, borderColor: `${color}99`, backgroundColor: `${color}22`,
      borderWidth: 1.5, pointRadius, pointHoverRadius: pointRadius + 2, tension: 0.25, fill: "-1" },
  ];
  if (avg) datasets.push({
    label: "Trung bình", data: avg, borderColor: color, backgroundColor: "transparent",
    borderWidth: 2.5, pointRadius, pointHoverRadius: pointRadius + 2, tension: 0.25,
  });

  const data: ChartData<"line"> = { labels, datasets };
  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: { legend: { display: true, labels: { color: AXIS.legend, boxWidth: 12, font: { size: 10 } } } },
    scales: {
      x: { ticks: { color: AXIS.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
      y: { ticks: { color: AXIS.tick }, grid: { color: AXIS.grid } },
    },
  };
  return <Line data={data} options={options} />;
}
