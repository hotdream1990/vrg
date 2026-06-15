/* Chuỗi cho 3 biểu đồ demo. Sinh DETERMINISTIC (không Math.random runtime) để ổn định
   giữa các lần render, nhưng giữ hình dạng "đi bộ ngẫu nhiên" khép tại giá đóng cửa thật. */

// Nhiễu giả ổn định trong [0,1) theo index + seed.
const noise = (i: number, seed: number): number => {
  const x = Math.sin((i + 1) * 12.9898 + seed * 78.233) * 43758.5453;
  return x - Math.floor(x);
};

// Đi bộ ngược từ giá đóng cửa thật (phải→trái), 30 điểm — như demo.
const walk = (end: number, vol: number, seed: number): number[] => {
  const a = new Array<number>(30);
  a[29] = end;
  for (let i = 28; i >= 0; i--) {
    a[i] = +(a[i + 1] - (noise(i, seed) - 0.46) * vol).toFixed(1);
  }
  return a;
};

export const priceDays = Array.from({ length: 30 }, (_, i) => `D${i + 1}`);
export const priceSeries: { label: string; color: string; data: number[] }[] = [
  { label: "OSE (RSS3)", color: "#22c55e", data: walk(2633.4, 12, 1) },
  { label: "SHANGHAI", color: "#38bdf8", data: walk(2628.9, 14, 2) },
  { label: "SGX", color: "#fbbf24", data: walk(2716.2, 18, 3) },
  { label: "MRE SMR20", color: "#a78bfa", data: walk(2308.0, 10, 4) },
];

// Lịch sử 20 ngày + dự báo 14 ngày kèm dải tin cậy.
const past = Array.from({ length: 20 }, (_, i) => +(2620 + Math.sin(i / 3) * 30 + (noise(i, 9) - 0.5) * 15).toFixed(1));
const lastPast = past[past.length - 1];
const fc = Array.from({ length: 14 }, (_, i) => +(lastPast + i * 4 + (noise(i, 11) - 0.5) * 8).toFixed(1));
export const forecast = {
  labels: [
    ...Array.from({ length: 20 }, (_, i) => `D-${20 - i}`),
    ...Array.from({ length: 14 }, (_, i) => `+${i + 1}`),
  ],
  line: [...past, ...fc],
  upper: [...past, ...fc].map((v, i) => (i < 20 ? null : +(v + 25 + i * 1.5).toFixed(1))),
  lower: [...past, ...fc].map((v, i) => (i < 20 ? null : +(v - 25 - i * 1.5).toFixed(1))),
};

// Cán cân cung-cầu 2025–2030 (số liệu Whatnext Rubber, cố định).
export const supplyDemand = {
  years: [2025, 2026, 2027, 2028, 2029, 2030],
  prod: [14.71, 14.948, 15.06, 15.113, 15.114, 15.118],
  dem: [15.567, 16.031, 16.479, 16.924, 17.352, 17.777],
  def: [-0.857, -1.083, -1.419, -1.811, -2.238, -2.659],
};
