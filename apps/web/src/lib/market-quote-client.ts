/* Client API Báo giá mủ thị trường (market_quote) — 1 phiếu/ngày, đọc/lưu/xoá. */

import { apiFetch } from "./http";

export type VcbRate = { mua_tm: number | null; mua_ck: number | null; ban: number | null };
export type Section = {
  prices: Record<string, number | null>;
  packaging: Record<string, string>; // grade -> bao bì (hàng rời/pallet)
  shipping: Record<string, string>; // grade -> đơn vị vận chuyển
  note: string;
};
export type DomesticVrgSection = Section & { status: Record<string, string> };
export type ProposalSection = {
  qty: Record<string, number | null>; // grade -> số lượng (tấn)
  prices: Record<string, number | null>; // grade -> đơn giá (VNĐ/tấn)
  note: string;
};

export type MarketQuote = {
  as_of: string;
  fx: VcbRate;
  domestic_private: Section;
  export_vrg: Section;
  domestic_vrg: DomesticVrgSection;
  customer_proposal: ProposalSection;
  regions: Record<string, number | null>; // mủ nước (đồng/độ TSC)
  regions_cup: Record<string, number | null>; // mủ chén (đồng/kg)
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

/** Gợi ý bao bì đóng gói (fallback nếu meta chưa tải). */
export const PACKAGING_OPTIONS = ["Hàng rời", "Pallet"];

const textMapEmpty = (m: Record<string, string>) => Object.values(m).every((v) => !v?.trim());
const numMapEmpty = (m: Record<string, number | null>) => Object.values(m).every((v) => v == null);

/** Phiếu "trống" (chưa có gì để lưu) — dùng để bỏ qua auto-save khi chưa nhập. */
export const isEmptyQuote = (q: MarketQuote): boolean => {
  const secEmpty = (s: Section) =>
    numMapEmpty(s.prices) && textMapEmpty(s.packaging) && textMapEmpty(s.shipping) && !s.note.trim();
  const fxEmpty = q.fx.mua_tm == null && q.fx.mua_ck == null && q.fx.ban == null;
  const statusEmpty = textMapEmpty(q.domestic_vrg.status);
  const propEmpty =
    numMapEmpty(q.customer_proposal.qty) && numMapEmpty(q.customer_proposal.prices)
    && !q.customer_proposal.note.trim();
  return fxEmpty && secEmpty(q.domestic_private) && secEmpty(q.export_vrg)
    && secEmpty(q.domestic_vrg) && statusEmpty && propEmpty
    && numMapEmpty(q.regions) && numMapEmpty(q.regions_cup) && !q.footer.trim();
};

/** Phiếu rỗng để tạo mới (giá theo chủng loại = null). */
export const emptyQuote = (as_of: string, grades: string[]): MarketQuote => {
  const blankNum = () => Object.fromEntries(grades.map((g) => [g, null]));
  return {
    as_of,
    fx: { mua_tm: null, mua_ck: null, ban: null },
    domestic_private: { prices: blankNum(), packaging: {}, shipping: {}, note: "" },
    export_vrg: { prices: blankNum(), packaging: {}, shipping: {}, note: "" },
    domestic_vrg: { prices: blankNum(), packaging: {}, shipping: {}, status: {}, note: "" },
    customer_proposal: { qty: blankNum(), prices: blankNum(), note: "" },
    regions: {},
    regions_cup: {},
    footer: "",
  };
};
