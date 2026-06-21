/* Data mẫu trích từ demo Dashboard_Gia_CaoSu.html — phần "khung" tĩnh của Command Center.
   Phần động (giá quét thật) lấy từ API, xem features/command-center/sections/LivePriceScan. */

export const topbar = {
  brandTitle: "Bizino AI · Rubber Price Intelligence",
  brandSub: "Hybrid AI Agent for VRG · Command Center v1.0 (PoC)",
  pills: [
    { kind: "live", text: "4/4 sàn đang Live" },
    { kind: "rag", text: "RAG: 1,284 tài liệu nội bộ" },
    { kind: "time", text: "15/05/2026 · 16:30 ICT" },
  ],
  avatar: "HN",
};

// to = route path (đã implement: "/" Dashboard, "/quet-da-san" Quét Đa sàn).
// hash = anchor cuộn trong trang Dashboard (các mục mockup, sẽ tách route sau).
export type NavItem = { icon: string; label: string; to: string; hash?: string };
export const nav: { section: string; items: NavItem[] }[] = [
  {
    section: "Điều hành",
    items: [
      { icon: "▣", label: "Dashboard", to: "/" },
      { icon: "⊞", label: "Hội tụ 4 sàn", to: "/", hash: "#sec-hoitu" },
      { icon: "⌖", label: "Ma trận Kịch bản", to: "/", hash: "#sec-kichban" },
      { icon: "⊜", label: "Giá sàn Tập đoàn", to: "/", hash: "#sec-giasan" },
      { icon: "▤", label: "Cung–cầu đến 2030", to: "/", hash: "#sec-cungcau" },
    ],
  },
  {
    section: "Phân tích AI",
    items: [
      { icon: "⧗", label: "Dự báo Đa khung", to: "/", hash: "#sec-kichban" },
      { icon: "⌘", label: "Rolling Forecast", to: "/", hash: "#sec-kichban" },
      { icon: "⊕", label: "Phát hiện bất thường", to: "/" },
      { icon: "⌬", label: "Private RAG / Chat", to: "/", hash: "#sec-rag" },
    ],
  },
  {
    section: "Dữ liệu & Báo cáo",
    items: [
      { icon: "◎", label: "Quét Đa sàn", to: "/quet-da-san" },
      { icon: "📋", label: "Bản tin ngày", to: "/ban-tin" },
      { icon: "⎙", label: "Tài liệu nội bộ", to: "/" },
      { icon: "◷", label: "Lịch sử Cảnh báo", to: "/" },
    ],
  },
  {
    section: "Quản lý số liệu",
    items: [
      { icon: "▦", label: "Bảng tính giá các sàn", to: "/quan-ly-so-lieu/bang-gia-san" },
      { icon: "⇄", label: "Tỷ giá", to: "/quan-ly-so-lieu/ty-gia" },
      { icon: "⊜", label: "Giá sàn Tập đoàn", to: "/quan-ly-so-lieu/gia-san-tap-doan" },
      { icon: "🪣", label: "Giá mủ nguyên liệu", to: "/quan-ly-so-lieu/gia-mu-nguyen-lieu" },
      { icon: "🏢", label: "Đơn vị thành viên", to: "/quan-ly-so-lieu/don-vi-thanh-vien" },
    ],
  },
  {
    section: "Quản trị",
    items: [
      { icon: "⌖", label: "Phân quyền RBAC", to: "/" },
      { icon: "⊞", label: "Cấu hình hệ thống", to: "/" },
    ],
  },
];

export const pageTitle = {
  h2: "Command Center · Phân tích thị trường Cao su",
  p: "Tổng hợp dữ liệu 4 sàn quốc tế · Báo cáo tuần 20/2026 (11–15/05) · Cập nhật rolling forecast cuối ngày",
};

export type Delta = "up" | "down" | "flat";
export const kpis: { label: string; value: string; delta: Delta; deltaText: string; sub: string }[] = [
  { label: "RSS3 - SGX (USD/tấn)", value: "2,716.2", delta: "up", deltaText: "▲ +2.02%", sub: "So với tuần 19 (2,662.4)" },
  { label: "SMR20 - MRE (USD/tấn)", value: "2,308.0", delta: "up", deltaText: "▲ +2.01%", sub: "Đỉnh tuần 13/5: 2,362.5" },
  { label: "LATEX (USD/tấn)", value: "1,952.8", delta: "up", deltaText: "▲ +2.12%", sub: "Sát ngưỡng 2,000 USD" },
  { label: "Mủ nước (VNĐ/độ TSC)", value: "510–553", delta: "flat", deltaText: "≈ Ổn định", sub: "Thu mua nội địa T20/2026" },
];

export type AlertKind = "danger" | "warn" | "info";
export const alerts: { kind: AlertKind; ico: string; title: string; desc: string; time: string }[] = [
  { kind: "danger", ico: "!", title: "Áp lực chốt lời từ quỹ đầu tư", desc: "OSE/SHFE giảm sâu phiên 14–15/5, xóa nhòa thành quả tăng", time: "2h" },
  { kind: "warn", ico: "⚠", title: "Rủi ro lũ quét Nam Thái Lan 16–18/5", desc: "Nguồn cung mủ có khả năng gián đoạn — lực đỡ giá", time: "5h" },
  { kind: "info", ico: "i", title: "AIRIA Ấn Độ kiến nghị nhập khẩu miễn thuế 6 tháng", desc: "Có thể kích cầu thu mua từ ĐNÁ trong trung hạn", time: "1d" },
  { kind: "info", ico: "i", title: "Butadien SHFE đi hình chữ V ngược", desc: "15,455 → 15,925 → 15,555 CNY/tấn — kéo theo CSTN", time: "1d" },
];

export const scenarios: { kind: "bull" | "base" | "bear"; title: string; arrow: string; prob: string; range: string; signals: string; reco: string }[] = [
  { kind: "bull", title: "BULL CASE", arrow: "↑", prob: "25%", range: "Tăng 5 – 15%", signals: "Tín hiệu: Dầu tăng, USD yếu, cầu phục hồi từ TQ", reco: "AI: Tăng giá sàn, ưu tiên HĐ giao ngay" },
  { kind: "base", title: "BASE CASE", arrow: "→", prob: "55%", range: "Đi ngang ±3%", signals: "Tín hiệu: Vĩ mô ổn định, cung-cầu cân bằng", reco: "AI: Giữ giá sàn, theo dõi sát Butadien" },
  { kind: "bear", title: "BEAR CASE", arrow: "↓", prob: "20%", range: "Giảm 5 – 12%", signals: "Tín hiệu: Tồn kho SHFE tăng, PMI giảm", reco: "AI: Giảm giá có kiểm soát, đẩy tiêu thụ tồn kho" },
];

export const forecastFrames: { title: string; desc: string; color: string }[] = [
  { title: "7 – 14 ngày", desc: "Chiến thuật giao ngay", color: "#22c55e" },
  { title: "1 – 3 tháng", desc: "Điều tiết tồn kho", color: "#38bdf8" },
  { title: "6 – 12 tháng", desc: "Phòng ngừa rủi ro, HĐ kỳ hạn", color: "#a78bfa" },
];
