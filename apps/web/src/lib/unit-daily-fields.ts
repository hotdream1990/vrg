/* Danh mục cột 2 biểu mẫu báo cáo tiêu thụ–tồn kho theo ngày (thu mua · tiêu thụ–tồn kho).
   THỨ TỰ CỘT GIỮ ĐÚNG NHƯ FILE EXCEL, kể cả cột suy ra (compute) nằm XEN GIỮA đúng vị trí.
   Bộ key input PHẢI khớp backend `app/services/unit_daily_fields.py`. */

import type { SaleLine } from "./unit-daily-consumption";

export type Kind = "purchase" | "consumption";
export type Values = Record<string, number | null | undefined>;
export type Column = {
  key: string;
  label: string;
  unit: string;              // đơn vị HIỂN THỊ
  group?: string;   // tiêu đề nhóm cột gộp (khớp header gộp của Excel)
  hint?: string;
  compute?: (v: Values, plan?: number | null) => number | null; // có = cột SUY RA (chỉ đọc)
  linked?: "latex" | "cup"; // đơn giá LINK từ "Giá mủ nguyên liệu" (nhập tay, đồng bộ kho)
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

export const KIND_LABEL: Record<Kind, string> = { purchase: "Thu mua", consumption: "Tiêu thụ – Tồn kho" };

const n = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);

// ── Thu mua — bám mẫu Excel "Chỉ tiêu Biểu (2)-ngày" (điểm THỜI ĐIỂM/ngày, KHÔNG lũy kế, KHÔNG %KH).
// Đây là cột cho BẢNG (danh sách/tổng hợp) — hiển thị số VND kết quả. Form NHẬP là PurchaseForm riêng
// (đơn vị nước ngoài nhập đơn giá nội tệ + USD + 2 tỷ giá, tự quy về VND). Tiền lưu BASE = đồng.
const _MU_NUOC = "Mủ nước";
const _MU_CHEN = "Mủ chén";
const _TT_TM = "Tiêu thụ mủ thu mua";
const PURCHASE: Column[] = [
  { key: "latex_wet", label: "Sản lượng thu mua", unit: "tấn", group: _MU_NUOC },
  { key: "price_latex", label: "Đơn giá thu mua", unit: "đồng/độ TSC", group: _MU_NUOC, linked: "latex" },
  { key: "coagulum", label: "Sản lượng thu mua", unit: "tấn", group: _MU_CHEN },
  { key: "price_cup", label: "Đơn giá thu mua", unit: "đồng/độ TSC", group: _MU_CHEN, linked: "cup" },
  { key: "consumption", label: "Sản lượng tiêu thụ", unit: "tấn", group: _TT_TM },
  // Doanh thu lưu BASE = đồng (VND), hiển thị "tỷ đồng" (scale 1e9). Giá BQ = Doanh thu(đồng) ÷ SL(tấn)
  // = đồng/tấn, hiển thị "triệu đ/tấn" (scale 1e6).
  { key: "revenue", label: "Doanh thu", unit: "tỷ đồng", group: _TT_TM, scale: 1_000_000_000 },
  { key: "price_avg", label: "Giá bán bình quân", unit: "triệu đ/tấn", group: _TT_TM, scale: 1_000_000,
    compute: (v) => (n(v.consumption) ? (n(v.revenue) ?? 0) / v.consumption! : null) },
];

// ── Tiêu thụ – Tồn kho ─────────────────────────────────────────────────────────────────
// TIÊU THỤ nhập theo BẢNG NHIỀU DÒNG (ConsumptionForm) — bảng chỉ hiển thị TỔNG HỢP suy ra từ `sales`
// (số lượng theo hình thức) + `revenue` (tổng doanh thu VND đã tính lúc lưu). TỒN KHO là ô phẳng.
const _TT = "Tiêu thụ (tổng hợp)";
const _TK = "Tồn kho";
const salesOf = (v: Values): SaleLine[] => {
  const s = (v as { sales?: unknown }).sales;
  return Array.isArray(s) ? (s as SaleLine[]) : [];
};
const salesQty = (v: Values, keep?: (l: SaleLine) => boolean): number =>
  salesOf(v).reduce((a, l) => a + (keep && !keep(l) ? 0 : (n(l.qty) ?? 0)), 0);
/** Tổng số lượng (kg) 1 bảng tồn kho (`stock_no_contract` | `stock_contract`). */
const stockKg = (v: Values, key: string): number => {
  const rows = (v as Record<string, unknown>)[key];
  return Array.isArray(rows) ? rows.reduce((a: number, r) => a + (n((r as { qty_kg?: number }).qty_kg) ?? 0), 0) : 0;
};

const CONSUMPTION: Column[] = [
  { key: "total_consumption", label: "Tổng tiêu thụ", unit: "tấn", group: _TT, compute: (v) => salesQty(v) },
  { key: "qty_export", label: "Tổng XK / UTXK", unit: "tấn", group: _TT, compute: (v) => salesQty(v, (l) => l.channel === "export") },
  { key: "qty_domestic", label: "Tổng nội tiêu", unit: "tấn", group: _TT, compute: (v) => salesQty(v, (l) => l.channel === "domestic") },
  { key: "revenue", label: "Doanh thu", unit: "tỷ đồng", group: _TT, scale: 1_000_000_000 },
  { key: "avg_price", label: "Giá bán bình quân", unit: "triệu đ/tấn", group: _TT, scale: 1_000_000,
    compute: (v) => { const q = salesQty(v); return q ? (n(v.revenue) ?? 0) / q : null; } },
  { key: "stock_no_contract_kg", label: "Tồn kho chưa HĐ", unit: "kg", group: _TK, compute: (v) => stockKg(v, "stock_no_contract") || null },
  { key: "stock_contract_kg", label: "Tồn kho đã HĐ", unit: "kg", group: _TK, compute: (v) => stockKg(v, "stock_contract") || null },
  { key: "stock_finished_kg", label: "Tồn kho thành phẩm", unit: "kg", group: _TK,
    compute: (v) => (stockKg(v, "stock_no_contract") + stockKg(v, "stock_contract")) || null },
  { key: "stock_material_kg", label: "Tồn kho nguyên liệu", unit: "kg", group: _TK },
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

/** Cột gộp Tổng cộng = đơn vị dòng chảy (tấn / tỷ đồng / triệu đồng); giá và % không gộp. */
export const isSummable = (unit: string): boolean =>
  unit === "tấn" || unit === "tỷ đồng" || unit === "triệu đồng";

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
      `Thu mua ${fmtNum(colValue(kind, "total_purchase", v), 1)}t`,
      n(v.consumption) != null ? `Tiêu thụ ${fmtNum(v.consumption, 1)}t` : null,
      n(v.revenue) != null ? `Giá BQ ${fmtNum(colDisplay(kind, "price_avg", v), 1)}` : null,
    ];
    return parts.filter(Boolean).join(" · ");
  }
  const parts = [
    `Tổng tiêu thụ ${fmtNum(colValue(kind, "total_consumption", v), 1)}t`,
    `Tồn kho TP ${fmtNum(v.stock_finished, 1)}t (chưa HĐ ${fmtNum(colValue(kind, "stock_no_hd", v), 1)}t)`,
  ];
  return parts.join(" · ");
}
