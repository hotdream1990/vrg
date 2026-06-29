import type { ChartData, ChartDataset, ChartOptions } from "chart.js";
import { Chart } from "react-chartjs-2";

import type { InventoryWeek } from "../../../lib/inventory-client";
import { AXIS } from "./chart-setup";

/** Cán cân tồn kho VRG: tồn kho + đã có hợp đồng (bar) · tồn tự do (line) — tấn, theo tuần. */
export default function InventoryBalanceChart({ weeks }: { weeks: InventoryWeek[] }) {
  const w = weeks.filter((x) => x.ton_kho != null).slice(-20); // 20 phiên (tuần) gần nhất cho gọn
  const labels = w.map((x) => x.as_of.slice(5).split("-").reverse().join("/")); // YYYY-MM-DD → DD/MM
  const free = w.map((x) =>
    x.ton_kho != null && x.ton_kho_hd != null ? x.ton_kho - x.ton_kho_hd : null,
  );

  const freeLine: ChartDataset<"line"> = {
    type: "line", label: "Tồn tự do (chưa có HĐ)", data: free,
    borderColor: "#ef4444", backgroundColor: "#ef444433", yAxisID: "y1",
    tension: 0.3, pointRadius: 2, pointBackgroundColor: "#ef4444", borderWidth: 2, order: 1,
  };

  const data: ChartData<"bar"> = {
    labels,
    datasets: [
      { type: "bar", label: "Tồn kho", data: w.map((x) => x.ton_kho), backgroundColor: "#38bdf8cc", borderRadius: 4, order: 2 },
      { type: "bar", label: "Đã có hợp đồng", data: w.map((x) => x.ton_kho_hd), backgroundColor: "#22c55ecc", borderRadius: 4, order: 2 },
      freeLine as unknown as ChartDataset<"bar">,
    ],
  };

  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { color: AXIS.legend, boxWidth: 14, font: { size: 11 } } } },
    scales: {
      x: { ticks: { color: AXIS.tick, autoSkip: true, maxTicksLimit: 10, maxRotation: 0 }, grid: { color: AXIS.grid } },
      y: { position: "left", ticks: { color: AXIS.tick }, grid: { color: AXIS.grid }, title: { display: true, text: "Tấn", color: AXIS.tick } },
      y1: { position: "right", ticks: { color: "#fca5a5" }, grid: { drawOnChartArea: false }, title: { display: true, text: "Tồn tự do (tấn)", color: "#fca5a5" } },
    },
  };

  return <Chart type="bar" data={data} options={options} />;
}
