/* Cột chồng theo MỐC (ngày hoặc tháng) + đường phụ trục phải — cho diễn biến thu mua · tiêu thụ.
   Khác `StackedDaysChart`: nhận sẵn `labels` (nên mốc THÁNG "MM/YYYY" hiện đúng) và giữ `null`
   trong dữ liệu — mốc chưa có số thì để trống, không vẽ thành cột 0. */

import type { ChartData, ChartOptions } from "chart.js";
import { Chart } from "react-chartjs-2";

import { AXIS } from "../../charts/chart-setup";
import type { ExtraLine } from "../../charts/StackedDaysChart";
import { fmtNum, fmtTon, withUnit } from "./dashboard-format";

export type TrendSeries = { label: string; data: (number | null)[]; color: string };

type Props = {
  labels: string[];
  series: TrendSeries[];
  unit?: string;
  /** Định dạng số của cột trong tooltip — mặc định theo luật tấn (1 số lẻ khi dưới 100). */
  format?: (v: number | null) => string;
  /** `zero`: trục phải bắt đầu từ 0 (doanh thu); giá thì để tự co cho thấy dao động. */
  line?: ExtraLine & { digits?: number; zero?: boolean };
};

/** Nhãn trục: "DD/MM/YYYY" rút còn "DD/MM" cho gọn; nhãn tháng "MM/YYYY" giữ nguyên. */
const shortTick = (label: string) => (label.length === 10 ? label.slice(0, 5) : label);

export default function TrendBarChart({ labels, series, unit = "Tấn", format = fmtTon, line }: Props) {
  const datasets: ChartData<"bar" | "line">["datasets"] = series.map((s) => ({
    type: "bar" as const,
    label: s.label,
    data: s.data,
    backgroundColor: `${s.color}cc`,
    borderRadius: 3,
    stack: "trend",
    yAxisID: "y",
  }));
  if (line) datasets.push({
    type: "line" as const, label: line.label, data: line.data, yAxisID: "y1",
    borderColor: line.color ?? "#0f172a", backgroundColor: "transparent",
    borderWidth: 2, tension: 0.25, pointRadius: labels.length <= 31 ? 2.5 : 0, spanGaps: false,
  });

  const options: ChartOptions<"bar" | "line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: AXIS.legend, boxWidth: 12, font: { size: 10 } } },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const onLine = ctx.dataset.yAxisID === "y1";
            const v = ctx.parsed.y;
            const text = onLine ? fmtNum(v, line?.digits ?? 0) : format(v);
            return `${ctx.dataset.label}: ${withUnit(text, onLine ? line?.unit ?? "" : unit)}`.trim();
          },
        },
      },
    },
    scales: {
      x: { stacked: true, grid: { display: false },
           ticks: { color: AXIS.tick, autoSkip: true, maxTicksLimit: 12, maxRotation: 0,
                    callback: (v) => shortTick(labels[Number(v)] ?? "") } },
      y: { stacked: true, beginAtZero: true, ticks: { color: AXIS.tick }, grid: { color: AXIS.grid },
           title: { display: true, text: unit, color: AXIS.tick } },
      ...(line ? {
        y1: { position: "right" as const, beginAtZero: !!line.zero, ticks: { color: AXIS.tick },
              grid: { display: false },
              title: { display: true, text: line.unit, color: AXIS.tick } },
      } : {}),
    },
  };

  return <Chart type="bar" data={{ labels, datasets } as ChartData<"bar">}
                options={options as ChartOptions<"bar">} />;
}
