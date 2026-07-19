/* Số liệu TIÊU THỤ nhập theo BẢNG NHIỀU DÒNG (mỗi dòng = 1 lần thực hiện hợp đồng).
   Mẫu "Chỉ tiêu Biểu (1)-ngày": HĐ Dài hạn/Chuyến × XK-UTXK/Nội tiêu; tổng + giá BQ tự tính.
   Tiền lưu BASE = đồng (VND). Đơn vị nước ngoài: giá bán theo USD + tỷ giá USD→VND (quy về VND). */

export type SaleContract = "long_term" | "spot";       // loại HĐ: Dài hạn | Chuyến
export type SaleChannel = "export" | "domestic";       // hình thức: XK/UTXK | Nội tiêu

/** 1 dòng tiêu thụ. `price` = giá bán (đơn vị VN: triệu đ/tấn · nước ngoài: USD/tấn). */
export type SaleLine = {
  contract: SaleContract;
  channel: SaleChannel;
  grade: string;                 // loại mủ
  qty: number | null;            // số lượng (tấn)
  price: number | null;          // giá bán (triệu đ/tấn nội địa · USD/tấn nước ngoài)
};

/** Tồn kho thành phẩm CHƯA có HĐ: chủng loại · loại bành · số lượng (kg). */
export type StockNoContractLine = { grade: string; bale: string; qty_kg: number | null };
/** Tồn kho thành phẩm ĐÃ có HĐ: chủng loại · kg · đơn giá (như sales) · lịch giao · file HĐ. */
export type StockContractLine = {
  grade: string; qty_kg: number | null; price: number | null;
  delivery_date?: string | null;         // 'YYYY-MM-DD'
  file?: string | null; filename?: string | null;  // tên file lưu (uuid) + tên gốc hiển thị
};

/** Payload tiêu thụ–tồn kho: dòng bán + tồn kho (2 bảng) + nguyên liệu. Tỷ giá (nước ngoài) chung. */
export type ConsumptionData = {
  sales?: SaleLine[];
  fx_revenue?: number | null;            // tỷ giá USD→VND (nước ngoài)
  revenue?: number | null;               // tổng doanh thu tiêu thụ (đồng)
  stock_no_contract?: StockNoContractLine[];
  stock_contract?: StockContractLine[];
  stock_material_kg?: number | null;     // tồn kho nguyên liệu (đơn vị không nhà máy)
};

/** Loại bành (đóng gói) tồn kho. */
export const BALES: string[] = ["33,33 kg", "35 kg"];

/** Tổng số lượng (kg) 1 bảng tồn kho. */
export const stockKgTotal = (rows: { qty_kg: number | null }[] | undefined): number =>
  (rows ?? []).reduce((a, r) => a + (r.qty_kg ?? 0), 0);

export const CONTRACTS: { value: SaleContract; label: string }[] = [
  { value: "long_term", label: "Dài hạn" },
  { value: "spot", label: "Chuyến" },
];
export const CHANNELS: { value: SaleChannel; label: string }[] = [
  { value: "export", label: "XK / UTXK" },
  { value: "domestic", label: "Nội tiêu" },
];
/** Loại mủ (đồng bộ nhãn với nhóm tồn kho theo chủng loại). */
export const GRADES: string[] = [
  "SVR CV50/CV60", "SVR 10CV/20CV", "SVR L / 3L", "RSS",
  "SVR 5 / 5S", "SVR 10 / 20", "Latex (quy khô)", "Ngoại lệ / Skim", "Chủng loại khác",
];

const TY = 1_000_000_000;   // 1 tỷ đồng
const TRIEU = 1_000_000;    // 1 triệu đồng
const n = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);

/** Doanh thu 1 dòng, quy về BASE = đồng (VND). Nước ngoài = qty × giá(USD) × tỷ giá; nội địa = qty × giá(triệu) × 1e6. */
export function lineRevenueVnd(line: SaleLine, foreign: boolean, fx: number | null | undefined): number | null {
  if (n(line.qty) == null || n(line.price) == null) return null;
  const q = line.qty as number, p = line.price as number;
  return foreign ? (n(fx) == null ? null : q * p * (fx as number)) : q * p * TRIEU;
}

export type ConsumptionTotals = {
  qty: number; qtyExport: number; qtyDomestic: number;
  qtyLongTerm: number; qtySpot: number;
  revenueVnd: number;              // tổng doanh thu (đồng)
  avgPriceTrieu: number | null;    // giá bán BQ (triệu đ/tấn) = doanh thu ÷ tổng SL
};

/** Cộng tổng các dòng tiêu thụ (SL theo hình thức/loại HĐ + doanh thu + giá BQ). */
export function totals(sales: SaleLine[] | undefined, foreign: boolean, fx: number | null | undefined): ConsumptionTotals {
  const t: ConsumptionTotals = {
    qty: 0, qtyExport: 0, qtyDomestic: 0, qtyLongTerm: 0, qtySpot: 0, revenueVnd: 0, avgPriceTrieu: null,
  };
  for (const ln of sales ?? []) {
    const q = n(ln.qty) ?? 0;
    t.qty += q;
    if (ln.channel === "export") t.qtyExport += q; else if (ln.channel === "domestic") t.qtyDomestic += q;
    if (ln.contract === "long_term") t.qtyLongTerm += q; else if (ln.contract === "spot") t.qtySpot += q;
    t.revenueVnd += lineRevenueVnd(ln, foreign, fx) ?? 0;
  }
  t.avgPriceTrieu = t.qty > 0 ? t.revenueVnd / t.qty / TRIEU : null;
  return t;
}

export const toTyDong = (dong: number | null): number | null => (dong == null ? null : dong / TY);
