/* Client API Báo giá mủ thị trường (market_quote) — 1 phiếu/ngày, đọc/lưu/xoá. */

import { apiFetch } from "./http";

export type VcbRate = { mua_tm: number | null; mua_ck: number | null; ban: number | null };
export type Section = { prices: Record<string, number | null>; note: string };
export type DomesticVrgSection = Section & { status: Record<string, string> };

export type MarketQuote = {
  as_of: string;
  fx: VcbRate;
  domestic_private: Section;
  export_vrg: Section;
  domestic_vrg: DomesticVrgSection;
  regions: Record<string, number | null>;
  footer: string;
};

export type MarketQuoteSummary = { as_of: string; filled: number; updated: string | null };
export type MarketQuoteMeta = { grades: string[]; units: string[] };
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

/** Phiếu "trống" (chưa có gì để lưu) — dùng để bỏ qua auto-save khi chưa nhập. */
export const isEmptyQuote = (q: MarketQuote): boolean => {
  const secEmpty = (s: Section) => Object.values(s.prices).every((v) => v == null) && !s.note.trim();
  const fxEmpty = q.fx.mua_tm == null && q.fx.mua_ck == null && q.fx.ban == null;
  const statusEmpty = Object.values(q.domestic_vrg.status).every((v) => !v?.trim());
  const regionsEmpty = Object.values(q.regions).every((v) => v == null);
  return fxEmpty && secEmpty(q.domestic_private) && secEmpty(q.export_vrg)
    && secEmpty(q.domestic_vrg) && statusEmpty && regionsEmpty && !q.footer.trim();
};

/** Phiếu rỗng để tạo mới (giá theo chủng loại = null). */
export const emptyQuote = (as_of: string, grades: string[]): MarketQuote => {
  const blank = () => Object.fromEntries(grades.map((g) => [g, null]));
  return {
    as_of,
    fx: { mua_tm: null, mua_ck: null, ban: null },
    domestic_private: { prices: blank(), note: "" },
    export_vrg: { prices: blank(), note: "" },
    domestic_vrg: { prices: blank(), status: {}, note: "" },
    regions: {},
    footer: "",
  };
};
