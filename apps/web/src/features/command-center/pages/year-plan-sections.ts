/* Bố cục màn Kế hoạch năm: 7 nhóm · 25 chỉ tiêu (18 ô nhập + 6 tổng tự cộng + tổng doanh thu do server
   cộng) — đúng thứ tự bảng chỉ tiêu (plans/261009-ke-hoach-nam-chi-tieu-moi/phase-00).
   Tổng ở đây chỉ để HIỂN THỊ: không nằm trong PLAN_FIELDS/YearPlanRow/EMPTY_PLAN nên không lọt vào
   payload, diff đề nghị sửa hay thẻ chốt số liệu. */

import type { YearPlanRow } from "../../../lib/unit-daily-client";

type PlanKey = keyof YearPlanRow;
export type PlanTotalId =
  | "purchase_total" | "process_total" | "consume_total" | "revenue_total" | "stock_total" | "lt_total" | "spot_total";

/** `fallback` = ô đã lưu dùng khi mọi mục con trống (đơn vị cũ chỉ khai tổng doanh thu). */
export type PlanTotal = { id: PlanTotalId; title: string; short: string; parts: PlanKey[]; fallback?: PlanKey };

export const PLAN_TOTALS: Record<PlanTotalId, PlanTotal> = {
  purchase_total: {
    id: "purchase_total", title: "Tổng thu mua (tấn)", short: "Tổng thu mua (tấn)",
    parts: ["plan_tonnes", "plan_goods_tonnes"],
  },
  process_total: {
    id: "process_total", title: "Tổng chế biến (tấn)", short: "Tổng chế biến (tấn)",
    parts: ["plan_process_exploit_tonnes", "plan_process_purchase_tonnes"],
  },
  consume_total: {
    id: "consume_total", title: "Tổng tiêu thụ (tấn)", short: "Tổng tiêu thụ (tấn)",
    parts: ["plan_consume_exploit_tonnes", "plan_consume_purchase_tonnes", "plan_consume_goods_tonnes"],
  },
  // Server lưu thật `plan_revenue_ty` = tổng 3 mục con (luật 2, phase-01) — web cộng y hệt để hiện ngay khi gõ.
  revenue_total: {
    id: "revenue_total", title: "Kế hoạch doanh thu — tổng (tỷ đồng)", short: "KH doanh thu (tỷ đồng)",
    parts: ["plan_revenue_exploit_ty", "plan_revenue_purchase_ty", "plan_revenue_goods_ty"],
    fallback: "plan_revenue_ty",
  },
  stock_total: {
    id: "stock_total", title: "Tổng tồn kho thành phẩm cuối năm (tấn)", short: "Tổng tồn kho cuối năm (tấn)",
    parts: ["plan_stock_exploit_tonnes", "plan_stock_purchase_tonnes", "plan_stock_goods_tonnes"],
  },
  // Hợp đồng thực hiện trong năm = hợp đồng của năm + hợp đồng năm trước chuyển sang (09/10/2026).
  lt_total: {
    id: "lt_total", title: "Tổng HĐ dài hạn thực hiện trong năm (tấn)", short: "Tổng HĐ dài hạn trong năm (tấn)",
    parts: ["signed_lt_tonnes", "carry_lt_tonnes"],
  },
  spot_total: {
    id: "spot_total", title: "Tổng HĐ chuyến thực hiện trong năm (tấn)", short: "Tổng HĐ chuyến trong năm (tấn)",
    parts: ["plan_sales_spot_tonnes", "carry_spot_tonnes"],
  },
};

export type PlanSectionRow = { kind: "field"; key: PlanKey } | { kind: "total"; id: PlanTotalId };
export type PlanSection = { title: string; rows: PlanSectionRow[] };

const f = (key: PlanKey): PlanSectionRow => ({ kind: "field", key });
const t = (id: PlanTotalId): PlanSectionRow => ({ kind: "total", id });

export const PLAN_SECTIONS: PlanSection[] = [
  { title: "Khai thác", rows: [f("plan_exploit_tonnes")] },
  { title: "Thu mua", rows: [f("plan_tonnes"), f("plan_goods_tonnes"), t("purchase_total")] },
  { title: "Chế biến", rows: [f("plan_process_exploit_tonnes"), f("plan_process_purchase_tonnes"), t("process_total")] },
  {
    title: "Tiêu thụ",
    rows: [f("plan_consume_exploit_tonnes"), f("plan_consume_purchase_tonnes"), f("plan_consume_goods_tonnes"), t("consume_total")],
  },
  {
    title: "Doanh thu",
    rows: [f("plan_revenue_exploit_ty"), f("plan_revenue_purchase_ty"), f("plan_revenue_goods_ty"), t("revenue_total")],
  },
  {
    title: "Tồn kho thành phẩm cuối năm",
    rows: [f("plan_stock_exploit_tonnes"), f("plan_stock_purchase_tonnes"), f("plan_stock_goods_tonnes"), t("stock_total")],
  },
  {
    title: "Hợp đồng (đơn vị tự khai)",
    rows: [
      f("signed_lt_tonnes"), f("carry_lt_tonnes"), t("lt_total"),
      f("plan_sales_spot_tonnes"), f("carry_spot_tonnes"), t("spot_total"),
    ],
  },
];

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** Cộng các số có mặt (làm tròn 6 số lẻ như server); mọi số trống → `null` (không hiện 0). */
export function sumOrNull(values: unknown[]): number | null {
  const nums = values.map(num).filter((v): v is number => v != null);
  if (!nums.length) return null;
  return Math.round(nums.reduce((a, v) => a + v, 0) * 1e6) / 1e6;
}

/** Giá trị một dòng tổng của MỘT đơn vị + cờ `fromFallback` = đang hiện SỐ CŨ đã lưu (mọi mục con
    trống, đơn vị cũ chỉ khai tổng doanh thu). Chịu được bản ghi thiếu khoá (snapshot chốt số liệu cũ). */
export function totalInfo(row: Partial<YearPlanRow>, total: PlanTotal): { value: number | null; fromFallback: boolean } {
  const s = sumOrNull(total.parts.map((k) => row[k]));
  if (s != null || !total.fallback) return { value: s, fromFallback: false };
  const v = num(row[total.fallback]);
  return { value: v, fromFallback: v != null };
}

export const totalValue = (row: Partial<YearPlanRow>, total: PlanTotal): number | null => totalInfo(row, total).value;

/** Giá trị một dòng của bảng (ô nhập hoặc dòng tổng) cho một đơn vị. */
export const sectionRowValue = (row: Partial<YearPlanRow>, r: PlanSectionRow): number | null =>
  r.kind === "field" ? num(row[r.key]) : totalValue(row, PLAN_TOTALS[r.id]);

/** Khoá React ổn định cho một dòng. */
export const sectionRowId = (r: PlanSectionRow): string => (r.kind === "field" ? r.key : r.id);

/** Sau khi lưu có mục con doanh thu: server đặt `plan_revenue_ty` = tổng các con → web đồng bộ y hệt
    (không thì xoá hết mục con, tổng lại rơi về số cũ đã lưu). */
export function syncRevenueTotal(row: YearPlanRow, changed: Partial<YearPlanRow>): YearPlanRow {
  const { parts } = PLAN_TOTALS.revenue_total;
  if (!parts.some((k) => k in changed)) return row;
  return { ...row, plan_revenue_ty: sumOrNull(parts.map((k) => row[k])) };
}

type Obj = Record<string, unknown>;

/** Bảng so sánh Đề nghị sửa kế hoạch năm: đề nghị có mục con doanh thu → thêm dòng tổng `plan_revenue_ty`
    tính sẵn ở CẢ HAI phía, để người duyệt thấy tổng đổi (đơn vị cũ tổng 100, đề nghị DT khai thác 40 →
    100 → 40). `side` = một phía đã chiếu; `proposed` = các ô trong đề nghị; `record` = bản ghi đang lưu.
    Phía đề nghị ghép mục con vắng mặt từ `record` rồi cộng — đúng luật server (con thắng, không lấy số cũ). */
export function withRevenueTotalForDiff(side: Obj | null, proposed: Obj, record: Obj | null, isPayload: boolean): Obj | null {
  const total = PLAN_TOTALS.revenue_total;
  if (!side || !total.parts.some((k) => k in proposed)) return side;
  const value = isPayload
    ? sumOrNull(total.parts.map((k) => (k in proposed ? proposed[k] : record?.[k])))
    : totalValue((record ?? {}) as Partial<YearPlanRow>, total);
  return { ...side, plan_revenue_ty: value };
}
