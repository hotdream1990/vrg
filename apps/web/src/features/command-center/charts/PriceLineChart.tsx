import type { ChartData, ChartOptions } from "chart.js";
import { Line } from "react-chartjs-2";

import { priceDays, priceSeries } from "../../../data/chart-series";
import { AXIS } from "./chart-setup";

const data: ChartData<"line"> = {
  labels: priceDays,
  datasets: priceSeries.map((s) => ({
    label: s.label,
    data: s.data,
    borderColor: s.color,
    backgroundColor: `${s.color}22`,
    tension: 0.35,
    fill: false,
    pointRadius: 0,
    borderWidth: 2,
  })),
};

const options: ChartOptions<"line"> = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { labels: { color: AXIS.legend, boxWidth: 14, font: { size: 11 } } } },
  scales: {
    x: { ticks: { color: AXIS.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { color: AXIS.grid } },
    y: { ticks: { color: AXIS.tick }, grid: { color: AXIS.grid } },
  },
};

/** Diễn biến giá 4 sàn 30 ngày (khép tại giá đóng cửa thật tuần 20). */
export default function PriceLineChart() {
  return <Line data={data} options={options} />;
}
