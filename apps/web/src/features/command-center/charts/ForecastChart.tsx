import type { ChartData, ChartOptions } from "chart.js";
import { Line } from "react-chartjs-2";

import { forecast } from "../../../data/chart-series";
import { AXIS } from "./chart-setup";

const data: ChartData<"line"> = {
  labels: forecast.labels,
  datasets: [
    { label: "Upper band", data: forecast.upper, borderColor: "transparent", backgroundColor: "#22c55e22", fill: "+1", pointRadius: 0 },
    { label: "Lower band", data: forecast.lower, borderColor: "transparent", backgroundColor: "transparent", pointRadius: 0 },
    { label: "Lịch sử + Dự báo", data: forecast.line, borderColor: "#22c55e", backgroundColor: "transparent", tension: 0.3, pointRadius: 0, borderWidth: 2 },
  ],
};

const options: ChartOptions<"line"> = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { color: AXIS.tick, maxTicksLimit: 10 }, grid: { color: AXIS.grid } },
    y: { ticks: { color: AXIS.tick }, grid: { color: AXIS.grid } },
  },
};

/** Dự báo đa khung: lịch sử + dải tin cậy 14 ngày. */
export default function ForecastChart() {
  return <Line data={data} options={options} />;
}
