import type { ChartData, ChartOptions } from "chart.js";
import { Bar } from "react-chartjs-2";

import { AXIS } from "./chart-setup";

/** Biểu đồ cột so sánh giá hiện tại theo grade (vd LGM SMR · US cents/kg). */
export default function GradeBarChart(
  { labels, values, color = "#22c55e", unit = "US cents/kg" }:
  { labels: string[]; values: number[]; color?: string; unit?: string },
) {
  const data: ChartData<"bar"> = {
    labels,
    datasets: [{ label: unit, data: values, backgroundColor: `${color}cc`, borderRadius: 4 }],
  };

  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: AXIS.tick }, grid: { display: false } },
      y: { ticks: { color: AXIS.tick }, grid: { color: AXIS.grid } },
    },
  };

  return <Bar data={data} options={options} />;
}
