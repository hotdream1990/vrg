import type { ChartData, ChartOptions } from "chart.js";
import { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";

import { type PriceSheet, fetchSheet } from "../../../lib/api-client";
import { AXIS } from "./chart-setup";

// Các đường giá hội tụ (chỉ vẽ đường có dữ liệu thật; đường nào thiếu data → tự bỏ).
const SERIES = [
  { exchange: "OSE", grade: "RSS3", label: "OSE · RSS3", color: "#16a34a" },
  { exchange: "SHANGHAI", grade: "RSS3", label: "SHFE · RSS3", color: "#0ea5e9" },
  { exchange: "SGX", grade: "RSS3", label: "SGX · RSS3", color: "#ef4444" },
  { exchange: "SGX", grade: "TSR20", label: "SGX · TSR20", color: "#ec4899" },
  { exchange: "MRB", grade: "SMR20", label: "MRB · SMR20", color: "#a855f7" },
  { exchange: "MRB", grade: "LATEX", label: "MRB · Latex", color: "#f59e0b" },
];

const ddmm = (iso: string) => { const [, m, d] = iso.split("-"); return `${d}/${m}`; };
const nf = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 0 });

const options: ChartOptions<"line"> = {
  responsive: true,
  maintainAspectRatio: false,
  // Rê chuột vào bất kỳ vị trí ngày nào → hiện tooltip TẤT CẢ đường của phiên đó (không cần trúng điểm).
  interaction: { mode: "index", intersect: false },
  plugins: {
    legend: { labels: { color: AXIS.legend, boxWidth: 14, font: { size: 11 } } },
    tooltip: {
      callbacks: {
        label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y == null ? "—" : `${nf(ctx.parsed.y)} USD/T`}`,
      },
    },
  },
  scales: {
    x: { ticks: { color: AXIS.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { color: AXIS.grid } },
    y: { ticks: { color: AXIS.tick }, grid: { color: AXIS.grid } },
  },
};

/** Diễn biến giá các sàn (USD/T) — dữ liệu THẬT từ /api/prices/sheet (đã quy đổi theo ngày). */
export default function LiveConvergenceChart() {
  const [sheet, setSheet] = useState<PriceSheet | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => { fetchSheet({ days: 30 }).then(setSheet).catch(() => setErr(true)); }, []);

  if (err) return <div className="scan-empty">Không tải được dữ liệu giá.</div>;
  if (!sheet) return <div className="scan-empty">Đang tải dữ liệu…</div>;

  const dates = sheet.rows.map((r) => r.as_of).sort((a, b) => a.localeCompare(b));
  const colKey = (ex: string, gr: string) =>
    sheet.groups.find((g) => g.exchange.toUpperCase() === ex.toUpperCase())
      ?.cols.find((c) => c.grade.toUpperCase() === gr.toUpperCase())?.key;
  const byDate = (key: string) => {
    const m = new Map<string, number | null>();
    sheet.rows.forEach((r) => m.set(r.as_of, r.cells[key]?.usd ?? null));
    return dates.map((d) => m.get(d) ?? null);
  };

  const datasets = SERIES
    .map((s) => { const k = colKey(s.exchange, s.grade); return k ? { s, data: byDate(k) } : null; })
    .filter((x): x is { s: (typeof SERIES)[number]; data: (number | null)[] } => !!x && x.data.some((v) => v != null))
    .map(({ s, data }) => ({
      label: s.label, data, borderColor: s.color, backgroundColor: `${s.color}22`,
      tension: 0.35, fill: false, pointRadius: 0, pointHoverRadius: 4, borderWidth: 2, spanGaps: true,
    }));

  if (datasets.length === 0)
    return <div className="scan-empty">Chưa có dữ liệu giá sàn — vào "Quét Đa sàn" để quét.</div>;

  const data: ChartData<"line"> = { labels: dates.map(ddmm), datasets };
  return <Line data={data} options={options} />;
}
