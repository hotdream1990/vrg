/* Số liệu TIÊU THỤ nhập theo BẢNG NHIỀU DÒNG (mỗi dòng = 1 lần thực hiện hợp đồng).
   Mẫu "Chỉ tiêu Biểu (1)-ngày": HĐ Dài hạn/Chuyến × XK-UTXK/Nội tiêu; tổng + giá BQ tự tính.
   Tiền lưu BASE = đồng (VND). Đơn vị nước ngoài: giá bán theo USD + tỷ giá USD→VND (quy về VND). */

export type SaleContract = "long_term" | "spot";       // loại HĐ: Dài hạn | Chuyến
export type SaleChannel = "export" | "domestic";       // hình thức: XK/UTXK | Nội tiêu

/** Loại tiền người dùng CHỌN khi nhập giá (giá bán tiêu thụ · đơn giá tồn kho đã có HĐ). */
export type Ccy = "VND" | "USD";
export const CCYS: { value: Ccy; label: string }[] = [
  { value: "VND", label: "VND" },
  { value: "USD", label: "USD" },
];
/** Đơn vị hiển thị của ô giá theo loại tiền đã chọn. */
export const priceUnitOf = (ccy: Ccy): string => (ccy === "USD" ? "USD/tấn" : "triệu đ/tấn");

/** 1 dòng tiêu thụ. `price` = giá bán, đơn vị theo `sales_ccy` (VND→triệu đ/tấn · USD→USD/tấn). */
export type SaleLine = {
  contract: SaleContract;
  channel: SaleChannel;
  grade: string;                 // loại mủ
  qty: number | null;            // số lượng (tấn)
  price: number | null;          // giá bán (triệu đ/tấn khi VND · USD/tấn khi USD)
  invoice_date?: string | null;  // ngày xuất hoá đơn 'YYYY-MM-DD'
  file?: string | null;          // file bộ Hợp đồng đã upload (tên lưu uuid)
  filename?: string | null;      // tên gốc để hiển thị
};

/** Khối tồn kho chỉ có số lượng (khối 1 & 2): chủng loại · số lượng (TẤN). */
export type StockQtyLine = { grade: string; qty: number | null };
/** Khối 3 — đã ký HĐ chưa giao: chủng loại · tấn · đơn giá (theo `stock_ccy`) · lịch giao · HĐ scan. */
export type StockSignedLine = {
  grade: string; qty: number | null; price: number | null;
  delivery_date?: string | null;         // 'YYYY-MM-DD'
  file?: string | null; filename?: string | null;  // tên file lưu (uuid) + tên gốc hiển thị
};

/** Payload tiêu thụ–tồn kho. TỒN KHO = số THỜI ĐIỂM, chia 4 khối:
    1 chế biến chưa nhập kho · 2 đã nhập kho · 3 đã ký HĐ chưa giao · 4 nguyên liệu chưa sản xuất. */
export type ConsumptionData = {
  sales?: SaleLine[];
  sales_ccy?: Ccy;                        // loại tiền của giá bán
  stock_ccy?: Ccy;                        // loại tiền của đơn giá khối 3
  fx_revenue?: number | null;             // tỷ giá USD→VND (dùng chung khi chọn USD)
  revenue?: number | null;                // tổng doanh thu tiêu thụ (đồng)
  stock_not_warehoused?: StockQtyLine[];  // 1 — thành phẩm chế biến CHƯA nhập kho
  stock_warehoused?: StockQtyLine[];      // 2 — thành phẩm ĐÃ nhập kho
  stock_signed_undelivered?: StockSignedLine[]; // 3 — đã ký HĐ chưa giao (kèm HĐ scan)
  stock_material?: number | null;         // 4 — nguyên liệu chưa sản xuất (tấn)
};

/** Tổng số lượng (TẤN) 1 bảng tồn kho. */
export const stockTonnesTotal = (rows: { qty: number | null }[] | undefined): number =>
  (rows ?? []).reduce((a, r) => a + (r.qty ?? 0), 0);

export const CONTRACTS: { value: SaleContract; label: string }[] = [
  { value: "long_term", label: "Dài hạn" },
  { value: "spot", label: "Chuyến" },
];
export const CHANNELS: { value: SaleChannel; label: string }[] = [
  { value: "export", label: "XK / UTXK" },
  { value: "domestic", label: "Nội tiêu" },
];
/** Chủng loại mủ — TÁCH THEO TỪNG LOẠI y như bảng Giá sàn Tập đoàn (SVR CV 50 và SVR CV60 là
    2 loại riêng, không gộp), thêm "SVR 10CV / 20CV" + "Chủng loại khác" cho đủ biểu mẫu tuần.
    PHẢI khớp `UNIT_STOCK_GRADES` ở backend (app/core/market_meta.py). */
export const GRADES: string[] = [
  "SVR CV 50", "SVR CV60", "SVR L", "SVR 3L Mix", "SVR 3L", "SVR 5S", "SVR 5",
  "SVR 10 Mix", "SVR 10 / CSR 10", "SVR 20 / CSR 20", "RSS 3", "RSS 1", "LATEX", "Skim Block",
  "SVR 10CV / 20CV", "Chủng loại khác",
];

const TY = 1_000_000_000;   // 1 tỷ đồng
const TRIEU = 1_000_000;    // 1 triệu đồng
const n = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);

/** Doanh thu 1 dòng, quy về BASE = đồng (VND). USD = qty × giá(USD) × tỷ giá; VND = qty × giá(triệu) × 1e6. */
export function lineRevenueVnd(line: SaleLine, ccy: Ccy, fx: number | null | undefined): number | null {
  if (n(line.qty) == null || n(line.price) == null) return null;
  const q = line.qty as number, p = line.price as number;
  return ccy === "USD" ? (n(fx) == null ? null : q * p * (fx as number)) : q * p * TRIEU;
}

export type ConsumptionTotals = {
  qty: number; qtyExport: number; qtyDomestic: number;
  qtyLongTerm: number; qtySpot: number;
  revenueVnd: number;              // tổng doanh thu (đồng)
  avgPriceTrieu: number | null;    // giá bán BQ (triệu đ/tấn) = doanh thu ÷ tổng SL
};

/** Cộng tổng các dòng tiêu thụ (SL theo hình thức/loại HĐ + doanh thu + giá BQ). */
export function totals(sales: SaleLine[] | undefined, ccy: Ccy, fx: number | null | undefined): ConsumptionTotals {
  const t: ConsumptionTotals = {
    qty: 0, qtyExport: 0, qtyDomestic: 0, qtyLongTerm: 0, qtySpot: 0, revenueVnd: 0, avgPriceTrieu: null,
  };
  for (const ln of sales ?? []) {
    const q = n(ln.qty) ?? 0;
    t.qty += q;
    if (ln.channel === "export") t.qtyExport += q; else if (ln.channel === "domestic") t.qtyDomestic += q;
    if (ln.contract === "long_term") t.qtyLongTerm += q; else if (ln.contract === "spot") t.qtySpot += q;
    t.revenueVnd += lineRevenueVnd(ln, ccy, fx) ?? 0;
  }
  t.avgPriceTrieu = t.qty > 0 ? t.revenueVnd / t.qty / TRIEU : null;
  return t;
}

export const toTyDong = (dong: number | null): number | null => (dong == null ? null : dong / TY);
