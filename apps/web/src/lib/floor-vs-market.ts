/* So sánh Giá sàn Tập đoàn với giá thị trường — 1 NGUỒN dùng chung cho
   "So sánh Giá sàn vs Thị trường" (Heatmap) và nhận định AI (Bản tin biến động).

   Giá thị trường lấy từ lưới "Bảng tính giá" (/api/prices/sheet) thay vì /api/prices/board:
   sheet có giá THEO TỪNG NGÀY nên khi phiên mới nhất chưa có số (sàn nghỉ, chưa quét kịp)
   thì lùi dần về phiên gần nhất CÓ số — kèm luôn ngày của phiên đó để hiển thị minh bạch
   (không bao giờ gán giá phiên cũ thành giá của ngày hiện tại). */

import type { PriceSheet } from "./api-client";

/** Chủng loại giá sàn VRG → mã hàng thị trường để đối chiếu. */
export const FLOOR_MAP: Record<string, MarketKey> = {
  "RSS 3": "RSS3",
  "SVR 20 / CSR 20": "SMR20",
  LATEX: "LATEX",
  "SVR CV 50": "SMRCV",
  "SVR CV60": "SMRCV",
};

export type MarketKey = "RSS3" | "SMR20" | "LATEX" | "SMRCV";

/** Cột sheet dùng cho từng mã hàng, theo thứ tự ưu tiên (hết cột 1 mới sang cột 2). */
const MARKET_COLS: Record<MarketKey, [string, string][]> = {
  RSS3: [["OSE", "RSS3"], ["SHANGHAI", "RSS3"]],
  SMR20: [["MRB", "SMR20"], ["SGX", "TSR20"]],
  LATEX: [["MRB", "LATEX"]],
  SMRCV: [["MRB", "SMRCV"]],
};

export type MarketPrice = {
  usd: number;      // USD/tấn
  label: string;    // sàn lấy giá (vd "MRB", "SGX·TSR20")
  asOf: string;     // ngày của phiên lấy giá (ISO) — có thể cũ hơn hôm nay
};

/** Giá mới nhất CÓ số của 1 cột sheet (lùi dần về các phiên trước). */
function latestCell(sheet: PriceSheet, exchange: string, grade: string): { usd: number; asOf: string } | null {
  const col = sheet.groups
    .find((g) => g.exchange.toUpperCase() === exchange.toUpperCase())
    ?.cols.find((c) => c.grade.toUpperCase() === grade.toUpperCase());
  if (!col) return null;
  const rows = [...sheet.rows].sort((a, b) => b.as_of.localeCompare(a.as_of)); // mới nhất trước
  for (const r of rows) {
    const usd = r.cells[col.key]?.usd;
    if (usd != null) return { usd, asOf: r.as_of };
  }
  return null;
}

/** Giá thị trường của 1 mã hàng: phiên mới nhất có số, theo thứ tự ưu tiên sàn. */
export function marketPrice(sheet: PriceSheet, mkt: MarketKey): MarketPrice | null {
  for (const [ex, gr] of MARKET_COLS[mkt]) {
    const hit = latestCell(sheet, ex, gr);
    if (hit) return { usd: hit.usd, label: gr === mkt ? ex : `${ex}·${gr}`, asOf: hit.asOf };
  }
  return null;
}

export type FloorItemLike = { grade: string; fob_usd: number | null };
export type FloorVsMarket = {
  product: string;
  vrg: number;
  market: number;
  marketLabel: string;
  marketAsOf: string;
  diffPct: number;
};

/** Ghép biểu giá sàn với giá thị trường → danh sách dòng so sánh (bỏ dòng thiếu số). */
export function compareFloorVsMarket(items: FloorItemLike[], sheet: PriceSheet): FloorVsMarket[] {
  const out: FloorVsMarket[] = [];
  for (const it of items) {
    const mkt = FLOOR_MAP[it.grade];
    if (!mkt || it.fob_usd == null) continue;
    const m = marketPrice(sheet, mkt);
    if (!m) continue;
    out.push({
      product: it.grade,
      vrg: it.fob_usd,
      market: m.usd,
      marketLabel: m.label,
      marketAsOf: m.asOf,
      diffPct: ((it.fob_usd - m.usd) / m.usd) * 100,
    });
  }
  return out;
}
