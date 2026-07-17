/* Danh mục cột 2 biểu mẫu báo cáo tuần đơn vị (thu mua · tiêu thụ–tồn kho).
   THỨ TỰ CỘT GIỮ ĐÚNG NHƯ FILE EXCEL, kể cả cột suy ra (compute) nằm XEN GIỮA đúng vị trí.
   Bộ key input PHẢI khớp backend `app/services/unit_weekly_fields.py`. */

export type Kind = "purchase" | "consumption";
export type Values = Record<string, number | null | undefined>;
export type Column = {
  key: string;
  label: string;
  unit: string;
  group?: string;   // tiêu đề nhóm cột gộp (khớp header gộp của Excel)
  hint?: string;
  compute?: (v: Values, plan?: number | null) => number | null; // có = cột SUY RA (chỉ đọc)
};

export const KIND_LABEL: Record<Kind, string> = { purchase: "Thu mua", consumption: "Tiêu thụ – Tồn kho" };

const n = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);
const sum = (...xs: (number | null | undefined)[]): number | null => {
  const vals = xs.map(n);
  return vals.every((v) => v == null) ? null : vals.reduce<number>((a, v) => a + (v ?? 0), 0);
};

// ── Thu mua — đúng thứ tự cột Excel (C→I): mủ nước · mủ đông · lũy kế · %KH · tiêu thụ · doanh thu · giá BQ ──
const PURCHASE: Column[] = [
  { key: "latex_wet", label: "Mủ nước (trong tuần, quy khô)", unit: "tấn" },
  { key: "coagulum", label: "Mủ đông (trong tuần, quy khô)", unit: "tấn" },
  { key: "cum_purchase", label: "Lũy kế SL mủ thu mua", unit: "tấn" },
  { key: "pct_plan", label: "% Kế hoạch thực hiện", unit: "%",
    compute: (v, plan) => (plan && n(v.cum_purchase) != null ? (v.cum_purchase! / plan) * 100 : null) },
  { key: "cum_consumption", label: "Sản lượng tiêu thụ lũy kế", unit: "tấn" },
  { key: "cum_revenue", label: "Doanh thu tiêu thụ lũy kế", unit: "tỷ đồng" },
  { key: "price_cum", label: "Giá bán BQ lũy kế", unit: "tr.đ/tấn",
    compute: (v) => (n(v.cum_consumption) ? ((n(v.cum_revenue) ?? 0) * 1000) / v.cum_consumption! : null) },
];

// ── Tiêu thụ – Tồn kho — đúng thứ tự cột Excel (C→Z), cột suy ra (H,K,N) xen giữa đúng vị trí ──
const _LT = "Tiêu thụ HĐ dài hạn (lũy kế)";
const _SPOT = "Tiêu thụ HĐ chuyến (lũy kế)";
const _STOCK = "Thành phẩm tồn kho chưa có hợp đồng";
const CONSUMPTION: Column[] = [
  { key: "signed_lt_2026", label: "Tổng SL đã ký HĐ dài hạn 2026 (lũy kế)", unit: "tấn" },
  { key: "lt_export", label: "XK / UTXK", unit: "tấn", group: _LT },
  { key: "lt_domestic", label: "Nội tiêu", unit: "tấn", group: _LT },
  { key: "spot_export", label: "XK / UTXK", unit: "tấn", group: _SPOT },
  { key: "spot_domestic", label: "Nội tiêu", unit: "tấn", group: _SPOT },
  { key: "total_consumption", label: "Tổng tiêu thụ", unit: "tấn",
    compute: (v) => sum(v.lt_export, v.lt_domestic, v.spot_export, v.spot_domestic) },
  { key: "revenue", label: "Doanh thu cao su (lũy kế)", unit: "tỷ đồng" },
  { key: "price_week", label: "Giá bán BQ (trong tuần)", unit: "tr.đ/tấn" },
  { key: "price_cum", label: "Giá bán BQ (lũy kế)", unit: "tr.đ/tấn",
    compute: (v) => { const t = sum(v.lt_export, v.lt_domestic, v.spot_export, v.spot_domestic); return t ? ((n(v.revenue) ?? 0) * 1000) / t : null; } },
  { key: "stock_finished", label: "Tồn kho thành phẩm", unit: "tấn" },
  { key: "stock_finished_hd", label: "Trong đó đã có hợp đồng", unit: "tấn" },
  { key: "stock_no_hd", label: "Thành phẩm chưa có hợp đồng", unit: "tấn",
    compute: (v) => (n(v.stock_finished) != null && n(v.stock_finished_hd) != null ? v.stock_finished! - v.stock_finished_hd! : null) },
  { key: "g_cv", label: "SVR CV50/CV60", unit: "tấn", group: _STOCK },
  { key: "g_10cv20cv", label: "SVR 10CV/20CV", unit: "tấn", group: _STOCK },
  { key: "g_l3l", label: "SVR L / 3L", unit: "tấn", group: _STOCK },
  { key: "g_rss", label: "RSS", unit: "tấn", group: _STOCK },
  { key: "g_5_5s", label: "SVR 5 / 5S", unit: "tấn", group: _STOCK },
  { key: "g_10_20", label: "SVR 10 / 20", unit: "tấn", group: _STOCK },
  { key: "g_latex", label: "Latex (quy khô)", unit: "tấn", group: _STOCK },
  { key: "g_skim", label: "Ngoại lệ / Skim", unit: "tấn", group: _STOCK },
  { key: "g_other", label: "Chủng loại khác", unit: "tấn", group: _STOCK },
  { key: "stock_material", label: "Tồn kho nguyên liệu chưa HĐ", unit: "tấn", hint: "đơn vị chưa có nhà máy chế biến" },
  { key: "carry_lt_2025", label: "SL tiêu thụ HĐ dài hạn 2025→2026", unit: "tấn" },
  { key: "carry_spot_2025", label: "SL tiêu thụ HĐ chuyến 2025→2026", unit: "tấn" },
];

export const COLUMNS: Record<Kind, Column[]> = { purchase: PURCHASE, consumption: CONSUMPTION };

export const isDerived = (c: Column): boolean => typeof c.compute === "function";

/** Key các ô NHẬP TAY theo thứ tự (bỏ cột suy ra) — cho dò thay đổi + gửi payload. */
export const INPUT_KEYS: Record<Kind, string[]> = {
  purchase: PURCHASE.filter((c) => !isDerived(c)).map((c) => c.key),
  consumption: CONSUMPTION.filter((c) => !isDerived(c)).map((c) => c.key),
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

/** Cột gộp Tổng cộng = đơn vị dòng chảy (tấn / tỷ đồng); giá và % không gộp. */
export const isSummable = (unit: string): boolean => unit === "tấn" || unit === "tỷ đồng";

/** Giá trị 1 cột (suy ra → tính; nhập tay → lấy thẳng). */
export const colValue = (kind: Kind, key: string, v: Values, plan?: number | null): number | null => {
  const c = COLUMNS[kind].find((x) => x.key === key);
  if (!c) return null;
  return c.compute ? c.compute(v, plan) : (v[key] ?? null);
};

/** Dòng tóm tắt ngắn cho timeline (vài chỉ số chính của 1 đơn vị/tuần). */
export function summaryLine(kind: Kind, v: Values, plan?: number | null): string {
  if (kind === "purchase") {
    const week = (n(v.latex_wet) ?? 0) + (n(v.coagulum) ?? 0);
    const parts = [
      `TM tuần ${fmtNum(week, 1)}t`,
      `Lũy kế ${fmtNum(v.cum_purchase, 1)}t`,
      plan && n(v.cum_purchase) != null ? `KH ${fmtNum(colValue(kind, "pct_plan", v, plan), 1)}%` : null,
      n(v.cum_revenue) != null ? `Giá BQ ${fmtNum(colValue(kind, "price_cum", v, plan), 1)}` : null,
    ];
    return parts.filter(Boolean).join(" · ");
  }
  const parts = [
    `Tổng tiêu thụ ${fmtNum(colValue(kind, "total_consumption", v), 1)}t`,
    `Tồn kho TP ${fmtNum(v.stock_finished, 1)}t (chưa HĐ ${fmtNum(colValue(kind, "stock_no_hd", v), 1)}t)`,
  ];
  return parts.join(" · ");
}
