import type { ChartData, ChartOptions } from "chart.js";
import { Chart } from "react-chartjs-2";

import { AXIS } from "./chart-setup";

const vnum = (n: number, d = 0) => n.toLocaleString("vi-VN", { maximumFractionDigits: d });

/** Đơn giá + sản lượng trên cùng một khung: cột = sản lượng thu mua (trục phải, tấn),
 *  dải tô = khoảng giá thấp nhất–cao nhất giữa các đơn vị, đường đậm = giá trung bình (trục trái).
 *  Trục giá KHÔNG bắt đầu từ 0 để thấy rõ biến động vài đồng/độ; trục sản lượng thì có. */
export default function PriceVolumeChart(
  { labels, min, max, avg, qty, color = "#16AF67", unit = "", qtyLabel = "Sản lượng thu mua (tấn)" }:
  {
    labels: string[]; min: (number | null)[]; max: (number | null)[]; avg: (number | null)[];
    qty: (number | null)[]; color?: string; unit?: string; qtyLabel?: string;
  },
) {
  const pointRadius = labels.length <= 20 ? 3 : 0;
  const suffix = unit ? ` (${unit})` : "";
  // spanGaps: ngày lẻ thiếu giá thì nối liền qua, không cắt đường thành từng mẩu.
  const line = { yAxisID: "y", order: 1, tension: 0.25, pointRadius,
                 pointHoverRadius: pointRadius + 2, spanGaps: true };

  const data: ChartData<"bar" | "line"> = {
    labels,
    datasets: [
      { type: "bar", label: qtyLabel, data: qty, yAxisID: "y1", order: 2,
        backgroundColor: `${color}59`, borderColor: `${color}8c`, borderWidth: 1, borderRadius: 3 },
      { type: "line", label: `Thấp nhất${suffix}`, data: min, borderColor: `${color}99`,
        backgroundColor: "transparent", borderWidth: 1.5, ...line },
      { type: "line", label: "Cao nhất", data: max, borderColor: `${color}99`,
        backgroundColor: `${color}22`, borderWidth: 1.5, fill: "-1", ...line },
      { type: "line", label: "Trung bình", data: avg, borderColor: color,
        backgroundColor: "transparent", borderWidth: 2.5, ...line },
    ],
  };

  const options: ChartOptions<"bar" | "line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: AXIS.legend, boxWidth: 12, font: { size: 10 } } },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const v = ctx.parsed.y;
            if (v == null) return `${ctx.dataset.label}: —`;
            return ctx.dataset.yAxisID === "y1"
              ? `${ctx.dataset.label}: ${vnum(v, 1)} tấn`
              : `${ctx.dataset.label}: ${vnum(v, 1)}${unit ? ` ${unit}` : ""}`;
          },
        },
      },
    },
    scales: {
      x: { ticks: { color: AXIS.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
      y: { position: "left", ticks: { color: AXIS.tick }, grid: { color: AXIS.grid },
           title: { display: !!unit, text: unit, color: AXIS.tick } },
      y1: { position: "right", beginAtZero: true, ticks: { color: AXIS.tick }, grid: { display: false },
            title: { display: true, text: "Tấn", color: AXIS.tick } },
    },
  };

  return <Chart type="bar" data={data as ChartData<"bar">} options={options as ChartOptions<"bar">} />;
}
