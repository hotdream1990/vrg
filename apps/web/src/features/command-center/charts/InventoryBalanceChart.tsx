import type { ChartData, ChartOptions } from "chart.js";
import { Chart } from "react-chartjs-2";

import type { InventoryWeek } from "../../../lib/inventory-client";
import { AXIS } from "./chart-setup";

const fmt = (n: number) => n.toLocaleString("vi-VN");

/**
 * Cán cân tồn kho VRG — CỘT CHỒNG: "Đã ký hợp đồng" + "Tồn tự do" = Tồn kho tổng.
 * Đã ký HĐ là một phần CỦA tồn kho (đã có bên cam kết mua) → tồn tự do = tồn tổng − đã ký
 * (KHÔNG cộng 2 số). Đơn vị tấn, theo tuần.
 */
export default function InventoryBalanceChart({ weeks }: { weeks: InventoryWeek[] }) {
  const w = weeks
    .filter((x) => x.ton_kho != null)
    .slice()
    .sort((a, b) => a.as_of.localeCompare(b.as_of)) // API trả DESC → sort tăng dần
    .slice(-20); // 20 phiên (tuần) gần nhất
  const labels = w.map((x) => x.as_of.slice(5).split("-").reverse().join("/")); // YYYY-MM-DD → DD/MM
  const free = w.map((x) =>
    x.ton_kho != null && x.ton_kho_hd != null ? x.ton_kho - x.ton_kho_hd : null,
  );

  const data: ChartData<"bar"> = {
    labels,
    datasets: [
      { label: "Đã ký hợp đồng", data: w.map((x) => x.ton_kho_hd), backgroundColor: "#22c55ecc", borderRadius: 4, stack: "tk" },
      { label: "Tồn tự do (chưa ký)", data: free, backgroundColor: "#38bdf8cc", borderRadius: 4, stack: "tk" },
    ],
  };

  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: AXIS.legend, boxWidth: 14, font: { size: 11 } } },
      tooltip: {
        callbacks: {
          footer: (items) => {
            const t = w[items[0]?.dataIndex ?? 0]?.ton_kho;
            return t != null ? `Tồn kho tổng: ${fmt(t)} tấn` : "";
          },
        },
      },
    },
    scales: {
      x: { stacked: true, ticks: { color: AXIS.tick, autoSkip: true, maxTicksLimit: 10, maxRotation: 0 }, grid: { color: AXIS.grid } },
      y: { stacked: true, ticks: { color: AXIS.tick }, grid: { color: AXIS.grid }, title: { display: true, text: "Tấn", color: AXIS.tick } },
    },
  };

  return <Chart type="bar" data={data} options={options} />;
}
