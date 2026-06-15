/* Data mẫu (phần 2): heatmap, bảng VRG, kiến trúc, RAG, bảo mật… — trích từ demo. */

export type HmCell = { text: string; bg: string; color: string };
const E: HmCell = { text: "—", bg: "#1f2937", color: "#6b7280" };

export const heatmap: { cols: string[]; rows: { label: string; cells: HmCell[] }[] } = {
  cols: ["OSE", "SHANGHAI", "SGX", "MRE"],
  rows: [
    { label: "RSS3", cells: [
      { text: "-0.03%", bg: "#374151", color: "#cbd5e1" },
      { text: "-0.01%", bg: "#374151", color: "#cbd5e1" },
      { text: "+2.02%", bg: "#16a34a", color: "#fff" }, E,
    ] },
    { label: "TSR20", cells: [E, E, { text: "+1.64%", bg: "#22c55e", color: "#fff" }, E] },
    { label: "SMRCV", cells: [E, E, E, { text: "+2.24%", bg: "#15803d", color: "#fff" }] },
    { label: "SMR20", cells: [E, E, E, { text: "+2.01%", bg: "#16a34a", color: "#fff" }] },
    { label: "LATEX", cells: [E, E, E, { text: "+2.12%", bg: "#16a34a", color: "#fff" }] },
  ],
};

export type VrgRow = { product: string; vrg: string; market: string; diff: string; diffCls: "up" | "down" | "flat"; chip: string; chipCls: string };
export const vrgRows: VrgRow[] = [
  { product: "RSS3", vrg: "2,950.0", market: "2,984.1", diff: "+34.1", diffCls: "up", chip: "Tăng nhẹ", chipCls: "chip" },
  { product: "STR20", vrg: "2,520.0", market: "2,504.3", diff: "-15.7", diffCls: "down", chip: "Giữ", chipCls: "chip warn" },
  { product: "SMR20", vrg: "2,290.0", market: "2,306.2", diff: "+16.2", diffCls: "up", chip: "Tăng nhẹ", chipCls: "chip" },
  { product: "LATEX", vrg: "2,010.0", market: "1,995.1", diff: "-14.9", diffCls: "down", chip: "Giữ", chipCls: "chip warn" },
  { product: "Mủ nước (VNĐ)", vrg: "540", market: "510–553", diff: "trong dải", diffCls: "flat", chip: "Theo dõi", chipCls: "chip" },
];

export const tsr20 = {
  y2025: "2.000 – 2.800",
  y2026: "2.800 – 3.500",
  note: "📈 Từ 2027 giá có khả năng tăng tốc và bùng nổ theo đà thâm hụt nguồn cung kéo dài.",
};

export const layers: { n: 1 | 2 | 3 | 4 | 5; pill: string; desc: string; chip: string }[] = [
  { n: 1, pill: "DATA SOURCE", desc: "TOCOM · SICOM · SHFE · AFET · BCTM nội bộ · Dữ liệu vi mô", chip: "23 nguồn" },
  { n: 2, pill: "INGESTION", desc: "Crawler tự động · Kiểm soát chất lượng & làm sạch dữ liệu", chip: "99.6% OK" },
  { n: 3, pill: "AI PROCESSING", desc: "Định lượng (Prophet/XGBoost) + Định tính (LLM & RAG)", chip: "8 models" },
  { n: 4, pill: "ORCHESTRATION", desc: "Bizino Agent Framework · Phân quyền RBAC · Ngưỡng cảnh báo", chip: "12 agents" },
  { n: 5, pill: "PRESENTATION", desc: "Dashboard · Báo cáo tự động · Mobile App · Chatbot", chip: "Realtime" },
];

export const workflow: { step: number; color: string; title: string; desc: string }[] = [
  { step: 1, color: "#22c55e", title: "Khởi tạo độc lập · AI ẩn danh", desc: "Tự động xử lý hàng triệu điểm dữ liệu, sinh kịch bản dự báo & đề xuất giá sàn — không bị chi phối cảm xúc." },
  { step: 2, color: "#38bdf8", title: "Đối chiếu thực tế · Chuyên viên Tập đoàn", desc: "Tiếp nhận báo cáo AI, kết hợp tình hình tồn kho thực tế & đánh giá chéo dữ liệu giữa các đơn vị thành viên." },
  { step: 3, color: "#a78bfa", title: "Quyết định · Ban Lãnh đạo", desc: "Kiểm duyệt cuối cùng, phê duyệt phương án tối ưu, ban hành chính sách điều tiết giá sàn toàn hệ thống." },
];

export type RagMsg = { role: "user" | "ai"; text: string; cite?: string };
export const ragMessages: RagMsg[] = [
  { role: "user", text: "Tóm tắt diễn biến SGX tuần 20 và lý do giảm cuối tuần?" },
  { role: "ai", text: "Sàn SGX tuần 20/2026 tăng +2.02% đối với RSS3 (đạt 2,716.2 USD/tấn) và +1.64% với TSR20. Đà tăng đầu tuần được hỗ trợ bởi rủi ro nguồn cung Thái Lan và dầu Brent vượt mốc. Tuy nhiên, hai phiên cuối tuần (14–15/5) bị áp lực chốt lời từ quỹ đầu tư và việc các nhà máy lốp xe dừng mua do biên lợi nhuận hạ nguồn bị siết chặt — kéo giá quay đầu giảm sâu.", cite: "📎 Nguồn: Báo cáo phân tích tuần 20-2026.pdf · trang 2–3 · VRG_Khao_sat_Hien_trang.xlsx · Q12" },
  { role: "user", text: "Cán cân cung cầu 2026 theo Whatnext Rubber là bao nhiêu?" },
  { role: "ai", text: "Theo Whatnext Rubber (cập nhật T7&8/2024), thiếu hụt nguồn cung 2026 vượt 1 triệu tấn, và đến 2030 mức thiếu hụt đạt hơn 2.6 triệu tấn. Mức tăng sản lượng hàng năm chậm hơn so với nhu cầu — đây là yếu tố nền tảng hỗ trợ chu kỳ tăng giá 2024–2030.", cite: "📎 Nguồn: Thị trường cao su phục hồi đến 2030 - Cập nhật.docx · Phần \"Cập nhật cung-cầu\"" },
];

export const security: { ico: string; h4: string; p: string }[] = [
  { ico: "🔒", h4: "On-Premise 100%", p: "Dữ liệu không lưu chuyển ra ngoài hạ tầng Tập đoàn" },
  { ico: "⌬", h4: "RBAC Đa lớp", p: "Phân tách dữ liệu nghiêm ngặt giữa đơn vị thành viên" },
  { ico: "⊕", h4: "AES-256", p: "Mã hóa quân sự + PII Redaction tự động" },
];

export const kpiTargets: { label: string; value: string; pct: number }[] = [
  { label: "MAPE (sai số dự báo)", value: "2.4% / <3%", pct: 82 },
  { label: "Giảm thời gian tổng hợp BC", value: "76% / 80%", pct: 95 },
  { label: "Đề xuất AI được phê duyệt", value: "71% / 75%", pct: 94 },
];

export const channels: { label: string; status: string; cls: string }[] = [
  { label: "📧 Email · ban lãnh đạo", status: "Bật", cls: "chip" },
  { label: "💬 Zalo OA · chuyên viên", status: "Bật", cls: "chip" },
  { label: "✈ Telegram · nhóm trực", status: "Bật", cls: "chip" },
  { label: "📱 Mobile App push", status: "Pilot", cls: "chip warn" },
];

export const footer = {
  left: "© 2026 Bizino AI · Hybrid AI Agent for VRG · Phiên bản PoC – Giai đoạn 1",
  right: "Hạ tầng: ASUS Ascent GX10 · LLM API bảo mật cao · Sẵn sàng nâng cấp GPU Server",
};
