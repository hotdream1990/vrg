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

/** Mục 6 — giá mủ 1 đơn vị tư nhân: một giá, hoặc khoảng giá `price`–`price_max`. */
export type PrivatePrice = { price: number | null; price_max: number | null };
export type PrivateUnit = { id: number; name: string };

export type MarketQuote = {
  as_of: string;
  fx: VcbRate;
  domestic_private: Section;
  domestic_export: Section;
  export_vrg: Section;
  domestic_vrg: Section;
  customer_proposal: ProposalSection;
  private_prices: Record<string, PrivatePrice>; // Mục 6 — tên đơn vị tư nhân -> giá
  private_processing_cost?: number | null; // Mục 6 — chi phí gia công SVR 3L (đồng/tấn), null = mặc định
  footer: string;
};

export type MarketQuoteSummary = { as_of: string; filled: number; updated: string | null };
export type MarketQuoteMeta = { grades: string[]; packaging: string[]; private_units: PrivateUnit[] };
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

/** Giá mới nhất của 1 đơn vị tư nhân (khối Dashboard) — mỗi dòng có ngày giá riêng. */
export type PrivateUnitPrice = PrivatePrice & {
  name: string;
  as_of: string;
  processing_cost?: number | null;
  prev: (PrivatePrice & { as_of: string }) | null; // lần báo giá liền trước của chính đơn vị này
};
export type PrivateLatest = {
  window_days: number;
  rows: PrivateUnitPrice[];
  rule: { floor_premium_min: number; floor_premium_max: number }; // giá sàn hợp lý = giá thành + khoảng này
};

/** Giá mủ tư nhân mới nhất của từng đơn vị trong cửa sổ ngày (kèm lần báo liền trước). */
export const fetchPrivateLatest = () => req<PrivateLatest>(`/api/market-quote/private-latest`);

/** Thêm đơn vị tư nhân vào danh mục Mục 6 → danh mục mới. */
export const addPrivateUnit = (name: string) =>
  req<PrivateUnit[]>(`/api/market-quote/private-units`, { method: "POST", body: JSON.stringify({ name }) });

/** Xoá đơn vị tư nhân khỏi danh mục (chỉ quản trị viên) → danh mục mới. */
export const deletePrivateUnit = (id: number) =>
  req<PrivateUnit[]>(`/api/market-quote/private-units/${id}`, { method: "DELETE" });

/** Tên các dòng Mục 6 có Giá max nhỏ hơn Giá (khoảng giá ngược) — khớp kiểm tra ở máy chủ. */
export const invalidPrivateRows = (m: Record<string, PrivatePrice> | undefined): string[] =>
  Object.entries(m ?? {})
    .filter(([, r]) => r?.price != null && r?.price_max != null && r.price_max < r.price)
    .map(([name]) => name);

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

const privateEmpty = (m?: Record<string, PrivatePrice>) =>
  Object.values(m ?? {}).every((r) => r?.price == null && r?.price_max == null);

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
    && privateEmpty(q.private_prices) && !q.footer.trim();
};

// ── Lấy số liệu từ phiếu ngày trước (điền nhanh phiếu mới) ──
type NumMap = Record<string, number | null>;
type TxtMap = Record<string, string>;

/** Điền các ô SỐ còn trống từ phiếu nguồn (không đè ô đã có). → [kết quả, số ô đã điền] */
const fillNums = (dst: NumMap, src?: NumMap): [NumMap, number] => {
  const out = { ...dst };
  let n = 0;
  for (const [k, v] of Object.entries(src ?? {})) if (v != null && out[k] == null) { out[k] = v; n++; }
  return [out, n];
};
/** Điền các ô CHỮ còn trống (bao bì / vận chuyển / tình trạng). */
const fillTexts = (dst: TxtMap, src?: TxtMap): [TxtMap, number] => {
  const out = { ...dst };
  let n = 0;
  for (const [k, v] of Object.entries(src ?? {})) if (v?.trim() && !out[k]?.trim()) { out[k] = v; n++; }
  return [out, n];
};
/** Điền ô ghi chú nếu đang trống. → [ghi chú, 1 nếu vừa điền] */
const fillNote = (dst?: string, src?: string): [string, number] =>
  dst?.trim() ? [dst, 0] : src?.trim() ? [src, 1] : [dst ?? "", 0];

/** Điền giá mủ tư nhân cho đơn vị CHƯA có giá nào (không đè dòng đã nhập). */
const fillPrivate = (
  dst: Record<string, PrivatePrice>, src?: Record<string, PrivatePrice>,
): [Record<string, PrivatePrice>, number] => {
  const out = { ...dst };
  let n = 0;
  for (const [k, v] of Object.entries(src ?? {})) {
    const cur = out[k];
    if (v?.price != null && cur?.price == null && cur?.price_max == null) { out[k] = { ...v }; n++; }
  }
  return [out, n];
};

const fillSection = (dst: Section, src?: Section): [Section, number] => {
  const [prices, a] = fillNums(dst.prices ?? {}, src?.prices);
  const [packaging, b] = fillTexts(dst.packaging ?? {}, src?.packaging);
  const [shipping, c] = fillTexts(dst.shipping ?? {}, src?.shipping);
  const [status, d] = fillTexts(dst.status ?? {}, src?.status);
  const [note, e] = fillNote(dst.note, src?.note);
  return [{ ...dst, prices, packaging, shipping, status, note }, a + b + c + d + e];
};

/** Chép số liệu phiếu ngày trước sang phiếu đang mở — CHỈ điền ô còn TRỐNG (không đè số đã nhập).
 *  KHÔNG chép tỷ giá VCB — bấm "Lấy tỷ giá VCB" để lấy đúng ngày.
 *  → [phiếu sau khi điền, số ô đã điền] */
export const copyFromPrevQuote = (draft: MarketQuote, prev: MarketQuote): [MarketQuote, number] => {
  const [domestic_private, a] = fillSection(draft.domestic_private, prev.domestic_private);
  const [domestic_export, b] = fillSection(draft.domestic_export, prev.domestic_export);
  const [export_vrg, c] = fillSection(draft.export_vrg, prev.export_vrg);
  const [domestic_vrg, d] = fillSection(draft.domestic_vrg, prev.domestic_vrg);
  const [qty, e] = fillNums(draft.customer_proposal?.qty ?? {}, prev.customer_proposal?.qty);
  const [prices, f] = fillNums(draft.customer_proposal?.prices ?? {}, prev.customer_proposal?.prices);
  const [propNote, g] = fillNote(draft.customer_proposal?.note, prev.customer_proposal?.note);
  const [footer, h] = fillNote(draft.footer, prev.footer);
  const [private_prices, i] = fillPrivate(draft.private_prices ?? {}, prev.private_prices);
  const copyCost = draft.private_processing_cost == null && prev.private_processing_cost != null;
  return [{
    ...draft,
    domestic_private, domestic_export, export_vrg, domestic_vrg,
    customer_proposal: { ...draft.customer_proposal, qty, prices, note: propNote },
    private_prices,
    private_processing_cost: copyCost ? prev.private_processing_cost : draft.private_processing_cost,
    footer,
    // fx: giữ nguyên phiếu đang mở — KHÔNG lấy từ ngày khác.
  }, a + b + c + d + e + f + g + h + i + (copyCost ? 1 : 0)];
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
    private_prices: {},
    private_processing_cost: null,
    footer: "",
  };
};
