import type { ChartData, ChartOptions } from "chart.js";
import { Chart } from "react-chartjs-2";

import type { StockSeries } from "../../../lib/inventory-client";
import { dm } from "../../../lib/date";
import { AXIS } from "./chart-setup";

const fmt = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 0 });

/** Bảng màu cột chồng — 2 màu đầu giữ đúng ý nghĩa của chế độ "cơ cấu"
 *  (xanh lá = đã ký hợp đồng, xanh biển = tồn tự do), các màu sau dùng cho chủng loại/khu vực. */
const PALETTE = ["#22c55e", "#38bdf8", "#f59e0b", "#a855f7", "#ef4444", "#14b8a6",
                 "#6366f1", "#84cc16", "#f472b6"];

/** Tồn kho Tập đoàn theo NGÀY — cột chồng, mỗi cột = tổng tồn của các đơn vị có số ngày đó.
 *  Mỗi ngày là một ảnh chụp độc lập (không cộng dồn); tooltip nói rõ độ phủ đơn vị. */
export default function StockSeriesChart({ series }: { series: StockSeries }) {
  const rows = series.rows;
  const labels = rows.map((r) => dm(r.as_of));

  const data: ChartData<"bar"> = {
    labels,
    datasets: series.series.map((s, i) => ({
      label: s.label,
      data: rows.map((r) => r.values[s.key] ?? null),
      backgroundColor: `${PALETTE[i % PALETTE.length]}cc`,
      borderRadius: 3,
      stack: "tk",
    })),
  };

  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: AXIS.legend, boxWidth: 12, font: { size: 10 } } },
      tooltip: {
        callbacks: {
          label: (ctx) => `${ctx.dataset.label}: ${fmt(ctx.parsed.y ?? 0)} tấn`,
          footer: (items) => {
            const r = rows[items[0]?.dataIndex ?? 0];
            if (!r) return "";
            return `Tổng tồn: ${fmt(r.total ?? 0)} tấn · ${r.units_counted}/${r.units_expected} đơn vị có số`;
          },
        },
      },
    },
    scales: {
      x: { stacked: true, ticks: { color: AXIS.tick, autoSkip: true, maxTicksLimit: 10, maxRotation: 0 },
           grid: { display: false } },
      y: { stacked: true, ticks: { color: AXIS.tick }, grid: { color: AXIS.grid },
           title: { display: true, text: "Tấn", color: AXIS.tick } },
    },
  };

  return <Chart type="bar" data={data} options={options} />;
}
