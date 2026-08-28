/* Danh mục cột 2 biểu mẫu báo cáo tiêu thụ–tồn kho theo ngày (thu mua · tiêu thụ–tồn kho).
   THỨ TỰ CỘT GIỮ ĐÚNG NHƯ FILE EXCEL, kể cả cột suy ra (compute) nằm XEN GIỮA đúng vị trí.
   Bộ key input PHẢI khớp backend `app/services/unit_daily_fields.py`. */

import { CUP_PRICE_UNIT, LACE_PRICE_UNIT, LATEX_PRICE_UNIT } from "./purchase-price-unit";

export type Kind = "purchase" | "consumption";
export type Values = Record<string, number | null | undefined>;
export type Column = {
  key: string;
  label: string;
  unit: string;              // đơn vị HIỂN THỊ
  group?: string;   // tiêu đề nhóm cột gộp (khớp header gộp của Excel)
  hint?: string;
  compute?: (v: Values, plan?: number | null) => number | null; // có = cột SUY RA (chỉ đọc)
  // đơn giá LINK từ "Giá mủ nguyên liệu" (nhập tay, đồng bộ kho) — khoá khớp `UnitPurchasePrice`
  linked?: "latex" | "cup" | "lace";
  // Số ĐỒNG cho 1 đơn vị hiển thị. Tiền lưu BASE = đồng, hiển thị/nhập theo đơn vị này.
  // vd Doanh thu lưu đồng, hiển thị "triệu đồng" → scale = 1_000_000. Không set = 1 (không đổi).
  scale?: number;
};

/** base (đồng) → giá trị HIỂN THỊ theo đơn vị cột. */
export const toDisplay = (c: Column, base: number | null): number | null =>
  base == null ? null : base / (c.scale ?? 1);
/** giá trị người dùng NHẬP (đơn vị hiển thị) → base (đồng) để lưu. */
export const toBase = (c: Column, disp: number | null): number | null =>
  disp == null ? null : disp * (c.scale ?? 1);

export const KIND_LABEL: Record<Kind, string> = { purchase: "Thu mua", consumption: "Tồn kho" };

const n = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);

// ── Thu mua — bám mẫu Excel "Chỉ tiêu Biểu (2)-ngày" (điểm THỜI ĐIỂM/ngày, KHÔNG lũy kế, KHÔNG %KH).
// Đây là cột cho BẢNG (danh sách/tổng hợp) — hiển thị số VND kết quả. Form NHẬP là PurchaseForm riêng
// (đơn vị nước ngoài nhập đơn giá nội tệ + USD + 2 tỷ giá, tự quy về VND). Tiền lưu BASE = đồng.
const _MU_NUOC = "Mủ nước";
const _MU_CHEN = "Mủ chén";
const _MU_DAY = "Mủ dây";
const _TP = "Thu mua thành phẩm";
const _TT_TM = "Tiêu thụ mủ thu mua";
/** Bảng thu mua thành phẩm (nhiều dòng, mỗi dòng 1 chủng loại) → tổng SL + giá trị (đồng). */
const finishedRows = (v: Values): { qty?: number | null; price?: number | null; ccy?: string; fx?: number | null }[] => {
  const rows = (v as Record<string, unknown>).finished;
  return Array.isArray(rows) ? rows : [];
};
const finishedQty = (v: Values): number => finishedRows(v).reduce((a, r) => a + (n(r.qty) ?? 0), 0);
const finishedVnd = (v: Values): number =>
  finishedRows(v).reduce((a, r) => {
    const q = n(r.qty), p = n(r.price);
    if (q == null || p == null) return a;
    if ((r.ccy ?? "VND") === "VND") return a + q * p * 1_000_000;
    return n(r.fx) == null ? a : a + q * p * (r.fx as number);
  }, 0);

const PURCHASE: Column[] = [
  // Mủ nguyên liệu khai theo QUY KHÔ **theo DRC** (thành phẩm thì không) — ghi thẳng vào đơn vị
  // tính để người đọc bảng tổng hợp không phải đoán, giống nhãn ở phiếu nhập.
  { key: "latex_wet", label: "Sản lượng thu mua", unit: "tấn quy khô", group: _MU_NUOC },
  { key: "price_latex", label: "Đơn giá thu mua", unit: LATEX_PRICE_UNIT, group: _MU_NUOC, linked: "latex" },
  { key: "coagulum", label: "Sản lượng thu mua", unit: "tấn quy khô", group: _MU_CHEN },
  { key: "price_cup", label: "Đơn giá thu mua", unit: CUP_PRICE_UNIT, group: _MU_CHEN, linked: "cup" },
  { key: "lace", label: "Sản lượng thu mua", unit: "tấn quy khô", group: _MU_DAY },
  { key: "price_lace", label: "Đơn giá thu mua", unit: LACE_PRICE_UNIT, group: _MU_DAY, linked: "lace" },
  // Thu mua thành phẩm nhập theo CHỦNG LOẠI (bảng nhiều dòng) → bảng tổng hợp chỉ hiện số cộng lại.
  { key: "finished_qty", label: "Sản lượng thu mua", unit: "tấn", group: _TP,
    compute: (v) => finishedQty(v) || null },
  { key: "finished_price_avg", label: "Đơn giá bình quân", unit: "triệu đ/tấn", group: _TP,
    scale: 1_000_000, compute: (v) => (finishedQty(v) ? finishedVnd(v) / finishedQty(v) : null) },
  { key: "consumption", label: "Sản lượng tiêu thụ", unit: "tấn", group: _TT_TM },
  // Doanh thu lưu BASE = đồng (VND), hiển thị "tỷ đồng" (scale 1e9). Giá BQ = Doanh thu(đồng) ÷ SL(tấn)
  // = đồng/tấn, hiển thị "triệu đ/tấn" (scale 1e6).
  { key: "revenue", label: "Doanh thu", unit: "tỷ đồng", group: _TT_TM, scale: 1_000_000_000 },
  { key: "price_avg", label: "Giá bán bình quân", unit: "triệu đ/tấn", group: _TT_TM, scale: 1_000_000,
    compute: (v) => (n(v.consumption) ? (n(v.revenue) ?? 0) / v.consumption! : null) },
];

// ── Tiêu thụ – Tồn kho ─────────────────────────────────────────────────────────────────
// TIÊU THỤ chỉ còn MỘT nguồn: các LẦN GIAO của hợp đồng (khoá `c_*`, server gom sẵn).
//
// ⚠ Nhóm cột "Tiêu thụ (số cũ đã khai)" ĐÃ GỠ (20/08/2026). Nó đọc ô `revenue` chốt cứng lúc lưu
// phiếu nên KHÔNG đổi theo khi hợp đồng được sửa: đợt sửa đơn giá 10/08/2026 chỉnh trên hợp đồng
// mà ô đó vẫn giữ số sai, hai màn nói khác nhau và người dùng không lần ra được bản ghi lệch
// (Đồng Nai - Kratie 27/01/2026 hiện giá bán 45.406 thay vì 45,406 triệu đ/tấn).
// Mảng `sales`/`sales_own`/`revenue` VẪN NGUYÊN trong payload để tra cứu lịch sử — chỉ thôi hiển
// thị. Muốn xem lại thì truy vấn thẳng `unit_daily_report`.
const _TK = "Tồn kho";
/** Tổng số lượng (TẤN) 1 bảng tồn kho (`stock_no_contract` | `stock_contract`). */
const stockTonnes = (v: Values, key: string): number => {
  const rows = (v as Record<string, unknown>)[key];
  return Array.isArray(rows) ? rows.reduce((a: number, r) => a + (n((r as { qty?: number }).qty) ?? 0), 0) : 0;
};

/* Nhóm cột TIÊU THỤ — gom từ các LẦN GIAO của hợp đồng (server tính, gắn vào bản ghi dưới khoá
   `c_*`), CÙNG nguồn với màn Báo cáo tiêu thụ nên hai màn không thể nói khác nhau.
   Sản lượng là TẤN QUY KHÔ, đúng quy ước của mọi báo cáo tiêu thụ hiện hành. */
const _TT_HD = "Tiêu thụ (theo hợp đồng)";
const cField = (key: string) => (v: Values): number | null =>
  n((v as Record<string, unknown>)[key] as number | null | undefined);

const C_CONSUMPTION: Column[] = [
  { key: "c_qty", label: "Tổng tiêu thụ", unit: "tấn quy khô", group: _TT_HD, compute: cField("c_qty") },
  { key: "c_qty_export", label: "XK / UTXK", unit: "tấn quy khô", group: _TT_HD, compute: cField("c_qty_export") },
  { key: "c_qty_domestic", label: "Tiêu thụ trong nước", unit: "tấn quy khô", group: _TT_HD, compute: cField("c_qty_domestic") },
  // Nội bộ tách riêng vì tổng ĐÃ gồm nó: thiếu cột này thì Tổng ≠ XK + trong nước, đọc như lỗi.
  { key: "c_qty_internal", label: "Tiêu thụ nội bộ", unit: "tấn quy khô", group: _TT_HD, compute: cField("c_qty_internal") },
  { key: "c_revenue", label: "Doanh thu", unit: "tỷ đồng", group: _TT_HD, scale: 1_000_000_000, compute: cField("c_revenue") },
  { key: "c_avg_price", label: "Giá bán bình quân", unit: "triệu đ/tấn", group: _TT_HD, scale: 1_000_000, compute: cField("c_avg_price") },
];

const CONSUMPTION: Column[] = [
  // Mọi cột tiêu thụ đều là cột SUY RA nên không lọt vào `INPUT_KEYS` — form không gửi ngược lên,
  // và backend cũng không nhận (`unit_daily_fields.CONSUMPTION_FIELDS` là danh sách cho phép).
  ...C_CONSUMPTION,
  // Tồn kho = chỉ tiêu THỜI ĐIỂM (mẫu tuần mục 11–14), đơn vị TẤN — KHÔNG cộng dồn giữa các ngày.
  { key: "stock_not_warehoused_t", label: "Chế biến chưa nhập kho", unit: "tấn", group: _TK, compute: (v) => stockTonnes(v, "stock_not_warehoused") || null },
  { key: "stock_warehoused_t", label: "Đã nhập kho", unit: "tấn", group: _TK, compute: (v) => stockTonnes(v, "stock_warehoused") || null },
  { key: "stock_finished_t", label: "Tồn kho thành phẩm", unit: "tấn", group: _TK,
    compute: (v) => (stockTonnes(v, "stock_not_warehoused") + stockTonnes(v, "stock_warehoused")) || null },
  // Cam kết giao hàng — HỆ THỐNG TỰ TÍNH từ hợp đồng (`{qty, by_grade, items}`), báo RIÊNG:
  // không cộng vào "Tồn kho thành phẩm" và cũng không trừ ra.
  { key: "stock_signed_t", label: "Đã ký HĐ chưa giao", unit: "tấn quy khô", group: _TK,
    compute: (v) => n((v as Record<string, unknown>).stock_signed_undelivered
      ? ((v as Record<string, { qty?: number }>).stock_signed_undelivered.qty ?? null) : null) || null },
  { key: "stock_material", label: "Tồn kho nguyên liệu chưa sản xuất (quy khô)", unit: "tấn", group: _TK },
];

export const COLUMNS: Record<Kind, Column[]> = { purchase: PURCHASE, consumption: CONSUMPTION };

export const isDerived = (c: Column): boolean => typeof c.compute === "function";
export const isLinked = (c: Column): boolean => c.linked != null; // đơn giá link (chỉ đọc, không lưu)

/** Key các ô NHẬP TAY theo thứ tự (bỏ cột suy ra + cột link) — cho dò thay đổi + gửi payload. */
export const INPUT_KEYS: Record<Kind, string[]> = {
  purchase: PURCHASE.filter((c) => !isDerived(c) && !isLinked(c)).map((c) => c.key),
  consumption: CONSUMPTION.filter((c) => !isDerived(c) && !isLinked(c)).map((c) => c.key),
};

/** Gom cột theo `group` liên tiếp thành khối (dựng header gộp + form theo nhóm). */
export function segments(kind: Kind): { group?: string; cols: Column[] }[] {
  const out: { group?: string; cols: Column[] }[] = [];
  for (const c of COLUMNS[kind]) {
    const last = out[out.length - 1];
    if (c.group && last && last.group === c.group) last.cols.push(c);
    else out.push({ group: c.group, cols: [c] });
  }
  return out;
}

/** Số → chuỗi vi-VN (tối đa `digits` số lẻ). null/NaN → '—'. */
export const fmtNum = (v: number | null | undefined, digits = 2): string =>
  v == null || Number.isNaN(v) ? "—" : v.toLocaleString("vi-VN", { maximumFractionDigits: digits });

/** Số chữ số thập phân HIỂN THỊ theo đơn vị cột: **tấn (kể cả "tấn quy khô") = 3** (đơn vị lớn →
    cần chính xác tới kg, nếu chỉ 1-2 số lẻ thì 1,004 tấn bị hiện thành "1"), % = 1,
    còn lại (tiền quy đổi…) = 2. */
export const displayDigits = (unit: string): number =>
  unit.startsWith("tấn") ? 3 : unit === "%" ? 1 : 2;

/** Cột gộp Tổng cộng = đơn vị dòng chảy (tấn / tấn quy khô / tỷ đồng / triệu đồng); giá và % không gộp.
    "tấn quy khô" là đơn vị của 4 cột sản lượng mủ nguyên liệu — vẫn là dòng chảy nên cộng dồn được. */
export const isSummable = (unit: string): boolean =>
  unit === "tấn" || unit === "tấn quy khô" || unit === "tỷ đồng" || unit === "triệu đồng";

/** Giá trị 1 cột ở BASE (suy ra → tính; nhập tay → lấy thẳng). Tiền = đồng. */
export const colValue = (kind: Kind, key: string, v: Values, plan?: number | null): number | null => {
  const c = COLUMNS[kind].find((x) => x.key === key);
  if (!c) return null;
  return c.compute ? c.compute(v, plan) : (v[key] ?? null);
};

/** Giá trị 1 cột để HIỂN THỊ (đã đổi base→đơn vị hiển thị theo scale). */
export const colDisplay = (kind: Kind, key: string, v: Values, plan?: number | null): number | null => {
  const c = COLUMNS[kind].find((x) => x.key === key);
  return c ? toDisplay(c, colValue(kind, key, v, plan)) : null;
};

/** Dòng tóm tắt ngắn cho timeline (vài chỉ số chính của 1 đơn vị/ngày). */
export function summaryLine(kind: Kind, v: Values): string {
  if (kind === "purchase") {
    const parts = [
      `Thu mua ${fmtNum(colValue(kind, "total_purchase", v), 3)}t`,
      n(v.consumption) != null ? `Tiêu thụ ${fmtNum(v.consumption, 3)}t` : null,
      n(v.revenue) != null ? `Giá BQ ${fmtNum(colDisplay(kind, "price_avg", v), 1)}` : null,
    ];
    return parts.filter(Boolean).join(" · ");
  }
  const parts = [
    `Tổng tiêu thụ ${fmtNum(colValue(kind, "c_qty", v), 3)}t`,
    `Tồn kho TP ${fmtNum(colValue(kind, "stock_finished_t", v), 3)}t`,
    `Đã ký HĐ chưa giao ${fmtNum(colValue(kind, "stock_signed_t", v), 3)}t`,
  ];
  return parts.join(" · ");
}
