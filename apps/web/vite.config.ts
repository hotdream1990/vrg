import { readFileSync } from "node:fs";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Version hiển thị (footer, brand) lấy từ package.json — 1 nguồn sự thật, tự đúng khi bump+deploy.
const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8"));

// Cổng riêng VRG (5390) để tránh trùng; đổi qua WEB_PORT nếu cần.
export default defineConfig({
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
  plugins: [react()],
  server: { port: Number(process.env.WEB_PORT) || 5390, strictPort: false },
  // Dùng 1 bản React duy nhất (tránh "Invalid hook call" khi pre-bundle react-chartjs-2 / antd).
  resolve: { dedupe: ["react", "react-dom"] },
  optimizeDeps: {
    include: ["react", "react-dom", "react-router-dom", "chart.js", "react-chartjs-2",
      "antd", "@ant-design/icons"],
  },
});
