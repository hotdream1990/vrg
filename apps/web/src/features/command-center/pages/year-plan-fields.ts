/* Các ô Kế hoạch năm — dùng chung cho màn Kế hoạch năm, bảng chốt số liệu và bảng so sánh Đề nghị sửa. */

import type { EntryType } from "../../../lib/entry-types";
import type { YearPlanRow } from "../../../lib/unit-daily-client";

export type PlanField = { key: keyof YearPlanRow; title: string; short: string; width: number };

export const PLAN_FIELDS: PlanField[] = [
  // Khai thác = mủ từ vườn cây của chính đơn vị; thu mua = mua của dân → 2 chỉ tiêu riêng.
  { key: "plan_exploit_tonnes", title: "Kế hoạch khai thác (tấn)", short: "KH khai thác (tấn)", width: 220 },
  { key: "plan_tonnes", title: "Kế hoạch thu mua (tấn)", short: "KH thu mua (tấn)", width: 240 },
  { key: "plan_goods_tonnes", title: "Kế hoạch hàng hóa — thành phẩm mua ngoài (tấn)", short: "KH hàng hóa (tấn)", width: 240 },
  { key: "plan_sales_spot_tonnes", title: "Kế hoạch tiêu thụ — HĐ chuyến (tấn)", short: "KH tiêu thụ HĐ chuyến (tấn)", width: 240 },
  { key: "signed_lt_tonnes", title: "HĐ dài hạn đã ký (tấn)", short: "HĐ dài hạn đã ký (tấn)", width: 220 },
  { key: "carry_lt_tonnes", title: "HĐ dài hạn 2025 chuyển sang (tấn)", short: "HĐDH năm trước chuyển sang (tấn)", width: 220 },
  { key: "carry_spot_tonnes", title: "HĐ chuyến 2025 chuyển sang (tấn)", short: "HĐ chuyến năm trước chuyển sang (tấn)", width: 220 },
  // Ô TIỀN duy nhất của bảng — ghi rõ TỶ ĐỒNG ngay trên tiêu đề, cột còn lại đều là tấn nên không
  // ghi thì chắc chắn có người nhập nhầm sang tấn.
  { key: "plan_revenue_ty", title: "Kế hoạch doanh thu (tỷ đồng)", short: "KH doanh thu (tỷ đồng)", width: 220 },
];

/** Nhãn ô theo khoá — cho bảng so sánh Đề nghị sửa và bảng chốt số liệu. */
export const PLAN_LABELS: Record<string, string> = Object.fromEntries(PLAN_FIELDS.map((f) => [f.key, f.title]));

export const EMPTY_PLAN: YearPlanRow = {
  plan_exploit_tonnes: null, plan_tonnes: null, plan_goods_tonnes: null, plan_sales_spot_tonnes: null,
  signed_lt_tonnes: null, carry_lt_tonnes: null, carry_spot_tonnes: null, plan_revenue_ty: null,
};

/** Loại nhập liệu phụ trách từng ô (khớp backend `plan_field_type`). */
export const fieldEntryType = (key: keyof YearPlanRow): EntryType => (key === "plan_tonnes" ? "purchase" : "contract");

/** Các ô ĐÃ ĐỔI so với số đang lưu (null = xoá ô) — nội dung của một đề nghị sửa kế hoạch năm. */
export function changedPlanValues(
  row: YearPlanRow, saved: YearPlanRow, editable: (k: keyof YearPlanRow) => boolean,
): Partial<YearPlanRow> {
  const out: Partial<YearPlanRow> = {};
  for (const { key } of PLAN_FIELDS) {
    if (editable(key) && (row[key] ?? null) !== (saved[key] ?? null)) out[key] = row[key] ?? null;
  }
  return out;
}
