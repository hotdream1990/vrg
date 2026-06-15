import type { ChartData, ChartDataset, ChartOptions } from "chart.js";
import { Chart } from "react-chartjs-2";

import { supplyDemand } from "../../../data/chart-series";
import { AXIS } from "./chart-setup";

const deficit: ChartDataset<"line"> = {
  type: "line",
  label: "Thâm hụt",
  data: supplyDemand.def,
  borderColor: "#ef4444",
  backgroundColor: "#ef444433",
  yAxisID: "y1",
  tension: 0.3,
  pointRadius: 3,
  pointBackgroundColor: "#ef4444",
  borderWidth: 2,
  order: 1,
};

const data: ChartData<"bar"> = {
  labels: supplyDemand.years,
  datasets: [
    { type: "bar", label: "Sản xuất", data: supplyDemand.prod, backgroundColor: "#22c55ecc", borderRadius: 4, order: 2 },
    { type: "bar", label: "Nhu cầu", data: supplyDemand.dem, backgroundColor: "#38bdf8cc", borderRadius: 4, order: 2 },
    deficit as unknown as ChartDataset<"bar">,
  ],
};

const options: ChartOptions<"bar"> = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { labels: { color: AXIS.legend, boxWidth: 14, font: { size: 11 } } } },
  scales: {
    x: { ticks: { color: AXIS.tick }, grid: { color: AXIS.grid } },
    y: { position: "left", ticks: { color: AXIS.tick }, grid: { color: AXIS.grid }, title: { display: true, text: "Triệu tấn", color: AXIS.tick } },
    y1: { position: "right", min: -3, max: 0, ticks: { color: "#fca5a5" }, grid: { drawOnChartArea: false }, title: { display: true, text: "Thâm hụt", color: "#fca5a5" } },
  },
};

/** Cán cân cung–cầu thế giới 2025–2030 (bar SX/Cầu + line Thâm hụt). */
export default function SupplyDemandChart() {
  return <Chart type="bar" data={data} options={options} />;
}
