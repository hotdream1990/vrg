/* Cột NGANG cho cơ cấu (chủng loại · khu vực · đơn vị) — thay biểu đồ tròn (chart-setup không đăng
   ký ArcElement) và đọc được cả khi nhãn dài. Chiều cao tự giãn theo số dòng.
   Dòng chưa có số (null) vẫn giữ nhãn nhưng không có cột; rê chuột hiện "—". */

import type { ChartData, ChartOptions } from "chart.js";
import { Bar } from "react-chartjs-2";

import { AXIS } from "../../charts/chart-setup";

type Props = {
  title: string;
  labels: string[];
  values: (number | null)[];
  format: (v: number | null) => string;
  unit: string;
  color?: string;
  /** Dòng phụ trong tooltip của từng cột (giá BQ, doanh thu, ngày lấy số…). */
  notes?: (index: number) => string[];
  empty?: string;
};

const ROW_PX = 24;
const MIN_PX = 120;
const PAD_PX = 40;

export default function HBarChart({
  title, labels, values, format, unit, color = "#16AF67", notes, empty = "Chưa có số.",
}: Props) {
  const data: ChartData<"bar"> = {
    labels,
    datasets: [{ label: unit, data: values, backgroundColor: `${color}cc`,
                 hoverBackgroundColor: color, borderRadius: 3, maxBarThickness: 18 }],
  };

  const options: ChartOptions<"bar"> = {
    indexAxis: "y",
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => `${format(ctx.parsed.x ?? null)} ${unit}`,
          afterLabel: (ctx) => notes?.(ctx.dataIndex) ?? [],
        },
      },
    },
    scales: {
      x: { beginAtZero: true, ticks: { color: AXIS.tick }, grid: { color: AXIS.grid } },
      y: { ticks: { color: AXIS.tick, autoSkip: false, font: { size: 11 } }, grid: { display: false } },
    },
  };

  const height = Math.max(MIN_PX, labels.length * ROW_PX + PAD_PX);

  return (
    <div className="ud-hbar">
      <div className="ud-mini-title">{title}</div>
      {labels.length === 0 ? (
        <div className="scan-empty">{empty}</div>
      ) : (
        <div style={{ position: "relative", height }}>
          <Bar data={data} options={options} />
        </div>
      )}
    </div>
  );
}
