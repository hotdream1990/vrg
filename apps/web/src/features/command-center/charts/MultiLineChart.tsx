import type { ChartData, ChartOptions } from "chart.js";
import { Line } from "react-chartjs-2";

import { AXIS } from "./chart-setup";

type Series = { name: string; values: (number | null)[]; color?: string };
const PALETTE = ["#16AF67", "#2563eb", "#a855f7", "#f59e0b", "#ef4444", "#0891b2"];

/** Biểu đồ nhiều đường (labels chung). Dùng cho tỷ giá base-100 / chuỗi chuẩn hoá.
 *  legend=false khi có bộ bật/tắt riêng bên ngoài. */
export default function MultiLineChart(
  { labels, series, legend = true }: { labels: string[]; series: Series[]; legend?: boolean },
) {
  // Dữ liệu thưa (ít phiên) → hiện chấm điểm cho rõ; dày → ẩn chấm cho gọn.
  const pointRadius = labels.length <= 14 ? 3 : 0;
  const data: ChartData<"line"> = {
    labels,
    datasets: series.map((s, i) => ({
      label: s.name,
      data: s.values,
      borderColor: s.color ?? PALETTE[i % PALETTE.length],
      backgroundColor: "transparent",
      tension: 0.25,
      pointRadius,
      pointHoverRadius: pointRadius + 2,
      borderWidth: 2,
      spanGaps: true,
    })),
  };
  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: { legend: { display: legend, labels: { color: AXIS.legend, boxWidth: 12, font: { size: 10 } } } },
    scales: {
      x: { ticks: { color: AXIS.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { color: AXIS.grid } },
      y: { ticks: { color: AXIS.tick }, grid: { color: AXIS.grid } },
    },
  };
  return <Line data={data} options={options} />;
}
