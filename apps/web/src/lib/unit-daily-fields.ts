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

export const KIND_LABEL: Record<Kind, string> = { purchase: "Thu mua", consumption: "Tồn kho" };

const n = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);

// ── Thu mua — bám mẫu Excel "Chỉ tiêu Biểu (2)-ngày" (điểm THỜI ĐIỂM/ngày, KHÔNG lũy kế, KHÔNG %KH).
// Đây là cột cho BẢNG (danh sách/tổng hợp) — hiển thị số VND kết quả. Form NHẬP là PurchaseForm riêng
// (đơn vị nước ngoài nhập đơn giá nội tệ + USD + 2 tỷ giá, tự quy về VND). Tiền lưu BASE = đồng.
const _MU_NUOC = "Mủ nước";
const _MU_CHEN = "Mủ chén";
// 2 loại mủ nguyên liệu bổ sung (chốt 30/07/2026) — đơn giá tính RIÊNG từng loại, nhập theo đồng/kg
// và lưu thẳng trong payload (không đẩy vào kho "Giá mủ nguyên liệu" như mủ nước/mủ chén).
const _NL_CHEN = "Mủ NL nước chưa cán vắt (chén)";
const _NL_RSS = "Mủ NL đã cán vắt (RSS)";
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
  // Mủ nguyên liệu khai theo QUY KHÔ (thành phẩm thì không) — ghi thẳng vào đơn vị tính để người
  // đọc bảng tổng hợp không phải đoán, giống nhãn ở phiếu nhập.
  { key: "latex_wet", label: "Sản lượng thu mua", unit: "tấn quy khô", group: _MU_NUOC },
  { key: "price_latex", label: "Đơn giá thu mua", unit: "đồng/độ TSC", group: _MU_NUOC, linked: "latex" },
  { key: "coagulum", label: "Sản lượng thu mua", unit: "tấn quy khô", group: _MU_CHEN },
  // Mủ chén tính theo độ TSC hoặc độ DRC — đơn vị tự chọn ở form (`cup_basis`), nên nhãn cột để chung.
  { key: "price_cup", label: "Đơn giá thu mua", unit: "đồng/độ", group: _MU_CHEN, linked: "cup",
    hint: "theo độ TSC hoặc DRC — đơn vị tự chọn" },
  { key: "cup_raw", label: "Sản lượng thu mua", unit: "tấn quy khô", group: _NL_CHEN },
  { key: "cup_raw_price", label: "Đơn giá thu mua", unit: "đồng/kg", group: _NL_CHEN },
  { key: "rss_pressed", label: "Sản lượng thu mua", unit: "tấn quy khô", group: _NL_RSS },
  { key: "rss_pressed_price", label: "Đơn giá thu mua", unit: "đồng/kg", group: _NL_RSS },
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
// TIÊU THỤ nhập theo 2 BẢNG NHIỀU DÒNG (ConsumptionForm): `sales` = mủ thu mua · `sales_own` = mủ
// khai thác. Bảng chỉ hiển thị TỔNG HỢP GỘP CHUNG cả hai (số lượng theo hình thức) + `revenue`
// (tổng doanh thu VND đã tính lúc lưu). TỒN KHO là ô phẳng.
// Nhóm tiêu thụ = DỮ LIỆU CŨ (trước 30/07/2026). Từ nay tiêu thụ tính từ hợp đồng và xem ở màn
// "Báo cáo tiêu thụ"; cột ở đây chỉ để tra lại số đơn vị đã khai trước khi chuyển đổi.
const _TT = "Tiêu thụ (số cũ đã khai)";
const _TK = "Tồn kho";
/** Dòng bán của CẢ 2 bảng: mủ thu mua (`sales`) + mủ khai thác (`sales_own`) — tổng cộng chung. */
const salesOf = (v: Values): SaleLine[] => {
  const rec = v as Record<string, unknown>;
  return ["sales", "sales_own"].flatMap((k) => (Array.isArray(rec[k]) ? (rec[k] as SaleLine[]) : []));
};
const salesQty = (v: Values, keep?: (l: SaleLine) => boolean): number =>
  salesOf(v).reduce((a, l) => a + (keep && !keep(l) ? 0 : (n(l.qty) ?? 0)), 0);
/** Tổng số lượng (TẤN) 1 bảng tồn kho (`stock_no_contract` | `stock_contract`). */
const stockTonnes = (v: Values, key: string): number => {
  const rows = (v as Record<string, unknown>)[key];
  return Array.isArray(rows) ? rows.reduce((a: number, r) => a + (n((r as { qty?: number }).qty) ?? 0), 0) : 0;
};

const CONSUMPTION: Column[] = [
  { key: "total_consumption", label: "Tổng tiêu thụ", unit: "tấn", group: _TT, compute: (v) => salesQty(v) || null },
  { key: "qty_export", label: "Tổng XK / UTXK", unit: "tấn", group: _TT, compute: (v) => salesQty(v, (l) => l.channel === "export") || null },
  { key: "qty_domestic", label: "Tổng tiêu thụ trong nước", unit: "tấn", group: _TT, compute: (v) => salesQty(v, (l) => l.channel === "domestic") || null },
  { key: "revenue", label: "Doanh thu", unit: "tỷ đồng", group: _TT, scale: 1_000_000_000 },
  { key: "avg_price", label: "Giá bán bình quân", unit: "triệu đ/tấn", group: _TT, scale: 1_000_000,
    compute: (v) => { const q = salesQty(v); return q ? (n(v.revenue) ?? 0) / q : null; } },
  // Tồn kho = chỉ tiêu THỜI ĐIỂM (mẫu tuần mục 11–14), đơn vị TẤN — KHÔNG cộng dồn giữa các ngày.
  { key: "stock_not_warehoused_t", label: "Chế biến chưa nhập kho", unit: "tấn", group: _TK, compute: (v) => stockTonnes(v, "stock_not_warehoused") || null },
  { key: "stock_warehoused_t", label: "Đã nhập kho", unit: "tấn", group: _TK, compute: (v) => stockTonnes(v, "stock_warehoused") || null },
  { key: "stock_finished_t", label: "Tồn kho thành phẩm", unit: "tấn", group: _TK,
    compute: (v) => (stockTonnes(v, "stock_not_warehoused") + stockTonnes(v, "stock_warehoused")) || null },
  // Cam kết giao hàng — HỆ THỐNG TỰ TÍNH từ hợp đồng (`{qty, by_grade, items}`), báo RIÊNG:
  // không cộng vào "Tồn kho thành phẩm" và cũng không trừ ra.
  { key: "stock_signed_t", label: "Đã ký HĐ chưa giao", unit: "tấn", group: _TK,
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
    `Tổng tiêu thụ ${fmtNum(colValue(kind, "total_consumption", v), 3)}t`,
    `Tồn kho TP ${fmtNum(colValue(kind, "stock_finished_t", v), 3)}t`,
    `Đã ký HĐ chưa giao ${fmtNum(colValue(kind, "stock_signed_t", v), 3)}t`,
  ];
  return parts.join(" · ");
}
