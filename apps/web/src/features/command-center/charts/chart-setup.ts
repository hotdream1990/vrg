/* Đăng ký 1 lần các thành phần Chart.js dùng trong dashboard (tree-shakeable). */
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Title,
  Tooltip,
} from "chart.js";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  BarController,
  LineController,
  Filler,
  Legend,
  Tooltip,
  Title,
);

// Màu trục/chú thích cho nền SÁNG (xanh-trắng VRG).
export const AXIS = { tick: "#5f6f67", grid: "#e3e9e4", legend: "#16241d" } as const;
