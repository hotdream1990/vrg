import type { ChartData, ChartOptions } from "chart.js";
import { Chart } from "react-chartjs-2";

import { dm } from "../../../lib/date";
import type { SeriesKey, StackedRow } from "../../../lib/series-client";
import { AXIS } from "./chart-setup";

const fmt = (n: number, d = 0) => n.toLocaleString("vi-VN", { maximumFractionDigits: d });

/** Bảng màu cột chồng — 2 màu đầu dành cho các cách nhìn CHỈ CÓ 2 LỚP của tồn kho (xanh lá = lớp
 *  "phần chắc chắn": đã nhập kho · đã ký hợp đồng; xanh biển = lớp còn lại), các màu sau dùng cho
 *  chủng loại/khu vực/… Chú giải luôn hiện nên hai cách nhìn dùng chung màu không gây đọc nhầm. */
const PALETTE = ["#22c55e", "#38bdf8", "#f59e0b", "#a855f7", "#ef4444", "#14b8a6",
                 "#6366f1", "#84cc16", "#f472b6"];

/** Đường phụ vẽ trên trục phải (vd doanh thu tiêu thụ) — không tham gia cột chồng. */
export type ExtraLine = { label: string; data: (number | null)[]; unit: string; color?: string };

/**
 * Cột chồng theo NGÀY dùng chung cho thu mua · tồn kho · tiêu thụ.
 * Mỗi cột là số của riêng ngày đó (không cộng dồn); `footer` cho phép từng màn nói thêm
 * điều mà chỉ nó biết (độ phủ đơn vị, doanh thu, cảnh báo thiếu tỷ giá…).
 */
export default function StackedDaysChart(
  { rows, series, unit = "Tấn", digits = 0, extraLine, footer }:
  {
    rows: StackedRow[]; series: SeriesKey[]; unit?: string; digits?: number;
    extraLine?: ExtraLine; footer?: (row: StackedRow, index: number) => string;
  },
) {
  const labels = rows.map((r) => dm(r.as_of));
  const datasets: ChartData<"bar" | "line">["datasets"] = series.map((s, i) => ({
    type: "bar" as const,
    label: s.label,
    data: rows.map((r) => r.values[s.key] ?? null),
    backgroundColor: `${PALETTE[i % PALETTE.length]}cc`,
    borderRadius: 3,
    stack: "day",
    yAxisID: "y",
  }));
  if (extraLine) datasets.push({
    type: "line" as const, label: extraLine.label, data: extraLine.data, yAxisID: "y1",
    borderColor: extraLine.color ?? "#0f172a", backgroundColor: "transparent",
    borderWidth: 2, tension: 0.25, pointRadius: rows.length <= 20 ? 3 : 0, spanGaps: true,
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
            const v = ctx.parsed.y;
            const u = ctx.dataset.yAxisID === "y1" ? extraLine?.unit ?? "" : unit;
            return `${ctx.dataset.label}: ${v == null ? "—" : fmt(v, digits)} ${u}`.trim();
          },
          footer: (items) => {
            const i = items[0]?.dataIndex ?? 0;
            return rows[i] ? (footer?.(rows[i], i) ?? "") : "";
          },
        },
      },
    },
    scales: {
      x: { stacked: true, ticks: { color: AXIS.tick, autoSkip: true, maxTicksLimit: 10, maxRotation: 0 },
           grid: { display: false } },
      y: { stacked: true, ticks: { color: AXIS.tick }, grid: { color: AXIS.grid },
           title: { display: true, text: unit, color: AXIS.tick } },
      ...(extraLine ? {
        y1: { position: "right" as const, beginAtZero: true, ticks: { color: AXIS.tick },
              grid: { display: false },
              title: { display: true, text: extraLine.unit, color: AXIS.tick } },
      } : {}),
    },
  };

  return <Chart type="bar" data={{ labels, datasets } as ChartData<"bar">}
                options={options as ChartOptions<"bar">} />;
}
