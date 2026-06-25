import type { ChartData, ChartOptions } from "chart.js";
import { Line } from "react-chartjs-2";

import { AXIS } from "./chart-setup";

/** Backtest: đường giá sàn THỰC (đậm) vs DỰ BÁO mô hình (đứt) theo từng lần ban hành. */
export default function BacktestChart(
  { labels, actual, pred }: { labels: string[]; actual: number[]; pred: number[] },
) {
  const data: ChartData<"line"> = {
    labels: labels.map((l) => l.slice(2)), // YY-MM-DD -> MM-DD
    datasets: [
      {
        label: "Giá sàn thực (FOB USD/T)",
        data: actual,
        borderColor: "#16a34a",
        backgroundColor: "transparent",
        borderWidth: 3,
        tension: 0.25,
        pointRadius: 3,
        pointBackgroundColor: "#16a34a",
      },
      {
        label: "Dự báo mô hình",
        data: pred,
        borderColor: "#f59e0b",
        backgroundColor: "transparent",
        borderWidth: 2,
        borderDash: [6, 4],
        tension: 0.25,
        pointRadius: 3,
        pointBackgroundColor: "#f59e0b",
      },
    ],
  };

  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: { legend: { labels: { color: AXIS.legend, boxWidth: 14, font: { size: 11 } } } },
    scales: {
      x: { ticks: { color: AXIS.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 12 }, grid: { color: AXIS.grid } },
      y: { ticks: { color: AXIS.tick }, grid: { color: AXIS.grid }, title: { display: true, text: "FOB USD/T", color: AXIS.tick } },
    },
  };

  return <Line data={data} options={options} />;
}
