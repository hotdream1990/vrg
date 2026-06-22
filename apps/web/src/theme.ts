/* Theme Ant Design theo màu thương hiệu VRG (giữ nền tối, accent xanh VRG). */

import { theme as antdTheme, type ThemeConfig } from "antd";

export const VRG = {
  primary: "#16AF67",  // xanh emerald (logo)
  dark: "#0B6B3A",     // xanh đậm (header/sidebar)
  lime: "#6DC850",     // lime accent (banner)
  tint: "#A8E1C6",
};

export const vrgTheme: ThemeConfig = {
  algorithm: antdTheme.defaultAlgorithm, // SÁNG (xanh + trắng theo vrg.vn)
  token: {
    colorPrimary: VRG.primary,
    colorInfo: VRG.primary,
    colorLink: VRG.dark,
    borderRadius: 8,
    fontFamily:
      "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif",
    colorBgLayout: "#f4f6f5",
  },
  components: {
    Layout: {
      siderBg: VRG.dark,        // Sider xanh đậm VRG
      headerBg: "#ffffff",      // Header trắng
      bodyBg: "#f4f6f5",
      headerPadding: "0 20px",
    },
    // Sider nền xanh → dùng Menu "dark" (chữ sáng) cho dễ đọc.
    Menu: {
      darkItemBg: "transparent",
      darkSubMenuItemBg: "transparent",
      darkItemColor: "#d7ecdf",
      darkItemSelectedBg: "rgba(255,255,255,.16)",
      darkItemSelectedColor: "#ffffff",
      darkItemHoverColor: "#ffffff",
    },
  },
};
