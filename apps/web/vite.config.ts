import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Cổng riêng VRG (5390) để tránh trùng; đổi qua WEB_PORT nếu cần.
export default defineConfig({
  plugins: [react()],
  server: { port: Number(process.env.WEB_PORT) || 5390, strictPort: false },
  // Dùng 1 bản React duy nhất (tránh "Invalid hook call" khi pre-bundle react-chartjs-2 / antd).
  resolve: { dedupe: ["react", "react-dom"] },
  optimizeDeps: {
    include: ["react", "react-dom", "react-router-dom", "chart.js", "react-chartjs-2",
      "antd", "@ant-design/icons"],
  },
});
