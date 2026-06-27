import type { ChartData, ChartOptions } from "chart.js";
import { Line } from "react-chartjs-2";

import { AXIS } from "./chart-setup";

/** Backtest: giá sàn THỰC (đậm) vs DỰ BÁO (đứt); tùy chọn thêm Tồn kho tự do trên trục phụ. */
export default function BacktestChart(
  { labels, actual, pred, free }:
  { labels: string[]; actual: number[]; pred: number[]; free?: (number | null)[] },
) {
  const hasFree = !!free?.some((v) => v != null);
  const datasets: ChartData<"line">["datasets"] = [
    {
      label: "Giá sàn thực (FOB USD/T)", data: actual, borderColor: "#16a34a",
      backgroundColor: "transparent", borderWidth: 3, tension: 0.25, pointRadius: 3, pointBackgroundColor: "#16a34a",
    },
    {
      label: "Dự báo mô hình", data: pred, borderColor: "#f59e0b", backgroundColor: "transparent",
      borderWidth: 2, borderDash: [6, 4], tension: 0.25, pointRadius: 3, pointBackgroundColor: "#f59e0b",
    },
  ];
  if (hasFree) {
    datasets.push({
      label: "Tồn kho tự do (tấn, trục phải)", data: free as number[], borderColor: "#7c3aed",
      backgroundColor: "transparent", borderWidth: 2, tension: 0.25, pointRadius: 2,
      pointBackgroundColor: "#7c3aed", spanGaps: true, yAxisID: "y1",
    });
  }

  const options: ChartOptions<"line"> = {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: { legend: { labels: { color: AXIS.legend, boxWidth: 14, font: { size: 11 } } } },
    scales: {
      x: { ticks: { color: AXIS.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 12 }, grid: { color: AXIS.grid } },
      y: { ticks: { color: AXIS.tick }, grid: { color: AXIS.grid }, title: { display: true, text: "FOB USD/T", color: AXIS.tick } },
      ...(hasFree && {
        y1: {
          position: "right" as const, ticks: { color: "#7c3aed" }, grid: { drawOnChartArea: false },
          title: { display: true, text: "Tồn kho tự do (tấn)", color: "#7c3aed" },
        },
      }),
    },
  };

  return <Line data={{ labels: labels.map((l) => l.slice(2)), datasets }} options={options} />;
}
