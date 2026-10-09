/* Các ô Kế hoạch năm — dùng chung cho màn Kế hoạch năm, bảng chốt số liệu và bảng so sánh Đề nghị sửa.
   Thứ tự = bảng chỉ tiêu (plans/261009-ke-hoach-nam-chi-tieu-moi/phase-00). Nhóm + dòng tổng tự cộng ở
   `year-plan-sections.ts` — tổng KHÔNG nằm ở đây để không lọt vào payload, diff, thẻ chốt số liệu. */

import type { EntryType } from "../../../lib/entry-types";
import type { YearPlanRow } from "../../../lib/unit-daily-client";

/** `derived` = ô server tự tính (chỉ đọc): vẫn giữ trong danh sách để diff/chốt số liệu nhận, nhưng
    lưới không cho gõ và không bao giờ gửi lên server. */
export type PlanField = { key: keyof YearPlanRow; title: string; short: string; derived?: true };

export const PLAN_FIELDS: PlanField[] = [
  // Khai thác = mủ từ vườn cây của chính đơn vị (gồm nhượng quyền); thu mua = mua của dân → 2 chỉ tiêu riêng.
  { key: "plan_exploit_tonnes", title: "Kế hoạch khai thác — gồm nhượng quyền (tấn)", short: "KH khai thác (tấn)" },
  { key: "plan_tonnes", title: "Kế hoạch thu mua nguyên liệu (tấn)", short: "KH thu mua NL (tấn)" },
  { key: "plan_goods_tonnes", title: "Kế hoạch hàng hóa — thành phẩm mua ngoài (tấn)", short: "KH hàng hóa (tấn)" },
  { key: "plan_process_exploit_tonnes", title: "Chế biến mủ khai thác (tấn)", short: "Chế biến khai thác (tấn)" },
  { key: "plan_process_purchase_tonnes", title: "Chế biến mủ thu mua (tấn)", short: "Chế biến thu mua (tấn)" },
  { key: "plan_consume_exploit_tonnes", title: "Tiêu thụ khai thác (tấn)", short: "Tiêu thụ khai thác (tấn)" },
  { key: "plan_consume_purchase_tonnes", title: "Tiêu thụ thu mua (tấn)", short: "Tiêu thụ thu mua (tấn)" },
  { key: "plan_consume_goods_tonnes", title: "Tiêu thụ hàng hóa (tấn)", short: "Tiêu thụ hàng hóa (tấn)" },
  // Ô TIỀN — ghi rõ TỶ ĐỒNG ngay trên nhãn, ô còn lại đều là tấn nên không ghi thì dễ nhập nhầm sang tấn.
  { key: "plan_revenue_exploit_ty", title: "Doanh thu khai thác (tỷ đồng)", short: "DT khai thác (tỷ đồng)" },
  { key: "plan_revenue_purchase_ty", title: "Doanh thu thu mua (tỷ đồng)", short: "DT thu mua (tỷ đồng)" },
  { key: "plan_revenue_goods_ty", title: "Doanh thu hàng hóa (tỷ đồng)", short: "DT hàng hóa (tỷ đồng)" },
  // Server tự cộng 3 mục con mỗi lần lưu; đơn vị cũ chỉ có tổng thì giữ số cũ tới khi nhập mục con.
  { key: "plan_revenue_ty", title: "Kế hoạch doanh thu — tổng (tỷ đồng)", short: "KH doanh thu (tỷ đồng)", derived: true },
  { key: "plan_stock_exploit_tonnes", title: "Tồn kho thành phẩm cuối năm — khai thác (tấn)", short: "Tồn kho cuối năm — khai thác (tấn)" },
  { key: "plan_stock_purchase_tonnes", title: "Tồn kho thành phẩm cuối năm — thu mua (tấn)", short: "Tồn kho cuối năm — thu mua (tấn)" },
  { key: "plan_stock_goods_tonnes", title: "Tồn kho thành phẩm cuối năm — hàng hóa (tấn)", short: "Tồn kho cuối năm — hàng hóa (tấn)" },
  { key: "plan_sales_spot_tonnes", title: "Kế hoạch tiêu thụ — HĐ chuyến (tấn)", short: "KH tiêu thụ HĐ chuyến (tấn)" },
  { key: "signed_lt_tonnes", title: "HĐ dài hạn đã ký (tấn)", short: "HĐ dài hạn đã ký (tấn)" },
  { key: "carry_lt_tonnes", title: "HĐ dài hạn năm trước chuyển sang (tấn)", short: "HĐDH năm trước chuyển sang (tấn)" },
  { key: "carry_spot_tonnes", title: "HĐ chuyến năm trước chuyển sang (tấn)", short: "HĐ chuyến năm trước chuyển sang (tấn)" },
];

/** Tra ô theo khoá (lưới nhập, bảng chốt số liệu). */
export const PLAN_FIELD_BY_KEY = Object.fromEntries(PLAN_FIELDS.map((f) => [f.key, f])) as Record<keyof YearPlanRow, PlanField>;

/** Nhãn ô theo khoá — cho bảng so sánh Đề nghị sửa và bảng chốt số liệu. */
export const PLAN_LABELS: Record<string, string> = Object.fromEntries(PLAN_FIELDS.map((f) => [f.key, f.title]));

export const EMPTY_PLAN: YearPlanRow = {
  plan_exploit_tonnes: null, plan_tonnes: null, plan_goods_tonnes: null, plan_sales_spot_tonnes: null,
  signed_lt_tonnes: null, carry_lt_tonnes: null, carry_spot_tonnes: null, plan_revenue_ty: null,
  plan_process_exploit_tonnes: null, plan_process_purchase_tonnes: null,
  plan_consume_exploit_tonnes: null, plan_consume_purchase_tonnes: null, plan_consume_goods_tonnes: null,
  plan_revenue_exploit_ty: null, plan_revenue_purchase_ty: null, plan_revenue_goods_ty: null,
  plan_stock_exploit_tonnes: null, plan_stock_purchase_tonnes: null, plan_stock_goods_tonnes: null,
};

/** Loại nhập liệu phụ trách từng ô (khớp backend `plan_field_type`). */
export const fieldEntryType = (key: keyof YearPlanRow): EntryType => (key === "plan_tonnes" ? "purchase" : "contract");

/** Các ô ĐÃ ĐỔI so với số đang lưu (null = xoá ô) — nội dung một lần lưu hoặc một đề nghị sửa.
    Ô chỉ đọc (`derived`) không bao giờ có mặt: server tự tính. */
export function changedPlanValues(
  row: YearPlanRow, saved: YearPlanRow, editable: (k: keyof YearPlanRow) => boolean,
): Partial<YearPlanRow> {
  const out: Partial<YearPlanRow> = {};
  for (const { key, derived } of PLAN_FIELDS) {
    if (derived || !editable(key)) continue;
    if ((row[key] ?? null) !== (saved[key] ?? null)) out[key] = row[key] ?? null;
  }
  return out;
}
