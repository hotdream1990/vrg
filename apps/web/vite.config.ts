import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Cổng riêng VRG (5390) để tránh trùng; đổi qua WEB_PORT nếu cần.
export default defineConfig({
  plugins: [react()],
  server: { port: Number(process.env.WEB_PORT) || 5390, strictPort: false },
});
