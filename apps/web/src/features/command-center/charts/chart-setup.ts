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

export const AXIS = { tick: "#6b7c9c", grid: "#1f2c4a", legend: "#cbd5e1" } as const;
