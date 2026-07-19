/* Client API Báo giá mủ thị trường (market_quote) — 1 phiếu/ngày, đọc/lưu/xoá. */

import { apiFetch } from "./http";

export type VcbRate = { mua_tm: number | null; mua_ck: number | null; ban: number | null };
export type Section = {
  prices: Record<string, number | null>;
  packaging: Record<string, string>; // grade -> bao bì (hàng rời/pallet)
  shipping: Record<string, string>; // grade -> đơn vị vận chuyển
  status?: Record<string, string>; // grade -> tình trạng giao dịch (Mục 1-4)
  note: string;
};
export type ProposalSection = {
  qty: Record<string, number | null>; // grade -> số lượng (tấn)
  prices: Record<string, number | null>; // grade -> đơn giá (VNĐ/tấn)
  note: string;
};

export type MarketQuote = {
  as_of: string;
  fx: VcbRate;
  domestic_private: Section;
  domestic_export: Section;
  export_vrg: Section;
  domestic_vrg: Section;
  customer_proposal: ProposalSection;
  regions: Record<string, number | null>; // mủ nước (đồng/độ TSC)
  regions_cup: Record<string, number | null>; // mủ chén (đồng/độ TSC)
  footer: string;
};

export type MarketQuoteSummary = { as_of: string; filled: number; updated: string | null };
export type MarketQuoteMeta = { grades: string[]; units: string[]; packaging: string[] };
export type VcbRateResult = VcbRate & { date: string };

/** Gợi ý tình trạng giao dịch (chọn nhanh; vẫn cho tự nhập tuỳ ý). */
export const MARKET_STATUS_OPTIONS = [
  "Rất chậm", "Chậm", "Có giao dịch", "Bình thường", "Sôi động", "Không giao dịch",
];

const req = <T>(path: string, init?: RequestInit): Promise<T> =>
  apiFetch<T>(path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });

export const fetchQuoteMeta = () => req<MarketQuoteMeta>(`/api/market-quote/meta`);

export const listQuotes = (from?: string, to?: string) => {
  const q = new URLSearchParams();
  if (from) q.set("date_from", from);
  if (to) q.set("date_to", to);
  const qs = q.toString();
  return req<MarketQuoteSummary[]>(`/api/market-quote${qs ? `?${qs}` : ""}`);
};

export const getQuote = (as_of: string) => req<MarketQuote>(`/api/market-quote/${as_of}`);

export const saveQuote = (mq: MarketQuote) =>
  req<MarketQuote>(`/api/market-quote`, { method: "PUT", body: JSON.stringify(mq) });

export const deleteQuote = (as_of: string) =>
  req<{ deleted: string }>(`/api/market-quote/${as_of}`, { method: "DELETE" });

/** Lấy tỷ giá USD của Vietcombank realtime (mặc định hôm nay). */
export const fetchVcbRate = (date?: string) =>
  req<VcbRateResult>(`/api/market-quote/vcb-rate${date ? `?date=${date}` : ""}`);

// ── Lịch sử giá SVR thị trường (chuỗi thời gian 4 mục) — cho biểu đồ xu hướng ──
export type MqHistorySeries = { name: string; values: (number | null)[] };
export type MqHistorySection = {
  key: string; label: string; unit: string; labels: string[]; series: MqHistorySeries[];
};
export type MqPriceHistory = { sections: MqHistorySection[]; dates: string[] };

/** Lịch sử giá thị trường 4 mục (ngày × chủng loại) để vẽ đường xu hướng. */
export const fetchMarketPriceHistory = (days = 90) =>
  req<MqPriceHistory>(`/api/market-quote/history?days=${days}`);

/** Gợi ý bao bì đóng gói cho các chủng loại SVR (fallback nếu meta chưa tải). */
export const PACKAGING_OPTIONS = ["Hàng rời", "Pallet"];

/** Chủng loại dùng 2 lựa chọn bao bì cố định (chỉ áp dụng cho LATEX). */
export const LATEX_GRADE = "LATEX";
export const LATEX_PACKAGING_OPTIONS = ["Đã có bao bì", "Chưa có bao bì"];

const textMapEmpty = (m: Record<string, string>) => Object.values(m).every((v) => !v?.trim());
const numMapEmpty = (m: Record<string, number | null>) => Object.values(m).every((v) => v == null);

/** Phiếu "trống" (chưa có gì để lưu) — dùng để bỏ qua auto-save khi chưa nhập. */
export const isEmptyQuote = (q: MarketQuote): boolean => {
  const secEmpty = (s?: Section) =>
    !s || (numMapEmpty(s.prices ?? {}) && textMapEmpty(s.packaging ?? {})
      && textMapEmpty(s.shipping ?? {}) && textMapEmpty(s.status ?? {}) && !s.note?.trim());
  const fxEmpty = q.fx.mua_tm == null && q.fx.mua_ck == null && q.fx.ban == null;
  const propEmpty =
    numMapEmpty(q.customer_proposal.qty) && numMapEmpty(q.customer_proposal.prices)
    && !q.customer_proposal.note.trim();
  return fxEmpty && secEmpty(q.domestic_private) && secEmpty(q.domestic_export)
    && secEmpty(q.export_vrg) && secEmpty(q.domestic_vrg) && propEmpty
    && numMapEmpty(q.regions) && numMapEmpty(q.regions_cup) && !q.footer.trim();
};

/** Phiếu rỗng để tạo mới (giá theo chủng loại = null). */
export const emptyQuote = (as_of: string, grades: string[]): MarketQuote => {
  const blankNum = () => Object.fromEntries(grades.map((g) => [g, null]));
  return {
    as_of,
    fx: { mua_tm: null, mua_ck: null, ban: null },
    domestic_private: { prices: blankNum(), packaging: {}, shipping: {}, status: {}, note: "" },
    domestic_export: { prices: blankNum(), packaging: {}, shipping: {}, status: {}, note: "" },
    export_vrg: { prices: blankNum(), packaging: {}, shipping: {}, status: {}, note: "" },
    domestic_vrg: { prices: blankNum(), packaging: {}, shipping: {}, status: {}, note: "" },
    customer_proposal: { qty: blankNum(), prices: blankNum(), note: "" },
    regions: {},
    regions_cup: {},
    footer: "",
  };
};
