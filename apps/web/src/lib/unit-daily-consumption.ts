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

/** 1 dòng tiêu thụ. `price` = giá bán, đơn vị theo `sales_ccy` (VND→triệu đ/tấn · USD→USD/tấn).
    Dùng chung cho 2 bảng nhập tách riêng: mủ THU MUA (`sales`) và mủ KHAI THÁC (`sales_own`). */
export type SaleLine = {
  contract: SaleContract;
  channel: SaleChannel;
  grade: string;                  // loại mủ
  qty: number | null;             // số lượng (tấn)
  price: number | null;           // giá bán (triệu đ/tấn khi VND · USD/tấn khi USD)
  ccy?: Ccy;                      // loại tiền của DÒNG này (1 ngày có thể vừa bán USD vừa bán VNĐ)
  fx?: number | null;             // tỷ giá USD→VND của dòng này (chỉ cần khi ccy = USD)
  warehouse_date?: string | null; // ngày xuất kho 'YYYY-MM-DD'
  invoice_date?: string | null;   // ngày xuất hoá đơn 'YYYY-MM-DD'
  file?: string | null;           // file bộ Hợp đồng đã upload (tên lưu uuid)
  filename?: string | null;       // tên gốc để hiển thị
  wh_file?: string | null;        // phiếu xuất kho
  wh_filename?: string | null;
  inv_file?: string | null;       // hoá đơn
  inv_filename?: string | null;
};

/** 3 chứng từ đính kèm mỗi dòng bán — khớp `SALE_DOC_SLOTS` ở backend. */
export const SALE_DOCS: { fileKey: keyof SaleLine; nameKey: keyof SaleLine; label: string }[] = [
  { fileKey: "file", nameKey: "filename", label: "Bộ Hợp đồng" },
  { fileKey: "wh_file", nameKey: "wh_filename", label: "Phiếu xuất kho" },
  { fileKey: "inv_file", nameKey: "inv_filename", label: "Hoá đơn" },
];

/** 2 mốc ngày của mỗi dòng bán. */
export const SALE_DATES: { key: keyof SaleLine; label: string }[] = [
  { key: "warehouse_date", label: "Ngày xuất kho" },
  { key: "invoice_date", label: "Ngày xuất hoá đơn" },
];

/** Dòng bán rỗng (nút "Thêm dòng" của cả 2 bảng). */
export const emptySaleLine = (): SaleLine => ({
  contract: "long_term", channel: "export", grade: GRADES[0], qty: null, price: null,
  warehouse_date: null, invoice_date: null,
  file: null, filename: null, wh_file: null, wh_filename: null, inv_file: null, inv_filename: null,
});

/** Khối tồn kho chỉ có số lượng (khối 1 & 2): chủng loại · số lượng (TẤN). */
export type StockQtyLine = { grade: string; qty: number | null };
/** Khối 3 — đã ký hợp đồng: chủng loại · tấn · đơn giá (theo `stock_ccy`) · lịch giao · HĐ scan. */
export type StockSignedLine = {
  grade: string; qty: number | null; price: number | null;
  ccy?: Ccy; fx?: number | null;         // loại tiền + tỷ giá của DÒNG này
  delivery_date?: string | null;         // 'YYYY-MM-DD'
  file?: string | null; filename?: string | null;  // tên file lưu (uuid) + tên gốc hiển thị
};

/** Payload tiêu thụ–tồn kho. TIÊU THỤ = 2 bảng nhập tách riêng (`sales` mủ thu mua ·
    `sales_own` mủ khai thác), tổng hợp và `revenue` GỘP CHUNG cả hai.
    TỒN KHO = số THỜI ĐIỂM, chia 4 khối:
    1 chế biến chưa nhập kho · 2 đã nhập kho · 3 đã ký hợp đồng · 4 nguyên liệu chưa sản xuất (quy khô). */
export type ConsumptionData = {
  sales?: SaleLine[];                     // tiêu thụ mủ THU MUA
  sales_own?: SaleLine[];                 // tiêu thụ mủ KHAI THÁC — nhập riêng, tổng cộng chung
  sales_ccy?: Ccy;                        // loại tiền của giá bán
  stock_ccy?: Ccy;                        // loại tiền của đơn giá khối 3
  fx_revenue?: number | null;             // tỷ giá USD→VND (dùng chung khi chọn USD)
  revenue?: number | null;                // tổng doanh thu tiêu thụ (đồng)
  stock_not_warehoused?: StockQtyLine[];  // 1 — thành phẩm chế biến CHƯA nhập kho
  stock_warehoused?: StockQtyLine[];      // 2 — thành phẩm ĐÃ nhập kho
  stock_signed_undelivered?: StockSignedLine[]; // 3 — đã ký hợp đồng (kèm HĐ scan)
  stock_material?: number | null;         // 4 — nguyên liệu chưa sản xuất, quy khô (tấn)

  // ── Tiêu thụ mủ THU MUA và mủ THÀNH PHẨM (chuyển từ biểu Thu mua sang) ──
  // `*_raw` = số user gõ (tỷ đồng khi VND · USD khi USD); `*_revenue` = đã quy về đồng để báo cáo.
  purchased_sold_qty?: number | null;
  purchased_sold_raw?: number | null;
  purchased_sold_ccy?: Ccy;
  purchased_sold_fx?: number | null;
  purchased_sold_revenue?: number | null;
  finished_sold_qty?: number | null;
  finished_sold_raw?: number | null;
  finished_sold_ccy?: Ccy;
  finished_sold_fx?: number | null;
  finished_sold_revenue?: number | null;
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

/** Doanh thu 1 dòng, quy về BASE = đồng (VND) — loại tiền & tỷ giá lấy NGAY TRÊN DÒNG đó.
    USD = qty × giá(USD) × tỷ giá (thiếu tỷ giá → null, KHÔNG đoán); VND = qty × giá(triệu) × 1e6. */
export function lineRevenueVnd(
  line: { qty: number | null; price: number | null; ccy?: Ccy; fx?: number | null },
): number | null {
  if (n(line.qty) == null || n(line.price) == null) return null;
  const q = line.qty as number, p = line.price as number;
  if ((line.ccy ?? "VND") !== "USD") return q * p * TRIEU;
  return n(line.fx) == null ? null : q * p * (line.fx as number);
}

export type ConsumptionTotals = {
  qty: number; qtyExport: number; qtyDomestic: number;
  qtyLongTerm: number; qtySpot: number;
  revenueVnd: number;              // tổng doanh thu (đồng)
  avgPriceTrieu: number | null;    // giá bán BQ (triệu đ/tấn) = doanh thu ÷ tổng SL
};

/** Cộng tổng các dòng tiêu thụ (SL theo hình thức/loại HĐ + doanh thu + giá BQ). */
export function totals(sales: SaleLine[] | undefined): ConsumptionTotals {
  const t: ConsumptionTotals = {
    qty: 0, qtyExport: 0, qtyDomestic: 0, qtyLongTerm: 0, qtySpot: 0, revenueVnd: 0, avgPriceTrieu: null,
  };
  for (const ln of sales ?? []) {
    const q = n(ln.qty) ?? 0;
    t.qty += q;
    if (ln.channel === "export") t.qtyExport += q; else if (ln.channel === "domestic") t.qtyDomestic += q;
    if (ln.contract === "long_term") t.qtyLongTerm += q; else if (ln.contract === "spot") t.qtySpot += q;
    t.revenueVnd += lineRevenueVnd(ln) ?? 0;
  }
  t.avgPriceTrieu = t.qty > 0 ? t.revenueVnd / t.qty / TRIEU : null;
  return t;
}

export const toTyDong = (dong: number | null): number | null => (dong == null ? null : dong / TY);
