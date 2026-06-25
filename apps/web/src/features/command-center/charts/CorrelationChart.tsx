import type { ChartData, ChartOptions } from "chart.js";
import { Line } from "react-chartjs-2";

import { AXIS } from "./chart-setup";

type Series = { name: string; values: (number | null)[] };
const COLORS = ["#16a34a", "#38bdf8", "#a78bfa", "#fbbf24", "#f87171", "#2dd4bf"];

/** Chart tương quan: nhiều đường đã CHUẨN HOÁ base-100 (so xu hướng). Đường 0 = giá sàn (nổi bật),
 *  markIndex = vị trí lần đang chọn (chấm to). */
export default function CorrelationChart(
  { labels, series, markIndex }: { labels: string[]; series: Series[]; markIndex: number },
) {
  const data: ChartData<"line"> = {
    labels: labels.map((l) => l.slice(2)), // YY-MM-DD -> MM-DD (bỏ '20')
    datasets: series.map((s, i) => ({
      label: s.name,
      data: s.values,
      borderColor: COLORS[i % COLORS.length],
      backgroundColor: "transparent",
      tension: 0.25,
      fill: false,
      spanGaps: true,
      borderWidth: i === 0 ? 3 : 1.5,
      pointRadius: (ctx) => (i === 0 && ctx.dataIndex === markIndex ? 6 : 0),
      pointBackgroundColor: COLORS[i % COLORS.length],
    })),
  };

  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: { legend: { labels: { color: AXIS.legend, boxWidth: 14, font: { size: 11 } } } },
    scales: {
      x: { ticks: { color: AXIS.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }, grid: { color: AXIS.grid } },
      y: { ticks: { color: AXIS.tick }, grid: { color: AXIS.grid }, title: { display: true, text: "Chỉ số (base-100)", color: AXIS.tick } },
    },
  };

  return <Line data={data} options={options} />;
}
