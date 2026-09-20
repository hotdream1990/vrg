/* Biểu THU MUA — hai phần nhập theo BẢNG NHIỀU DÒNG:
   - Mủ NGUYÊN LIỆU (mủ nước · mủ chén · mủ dây): mỗi dòng {chủng loại · sản lượng quy khô};
     ĐƠN GIÁ KHÔNG đi theo dòng, vẫn MỘT giá cho cả loại mủ trong ngày.
   - Thu mua THÀNH PHẨM (mua lại mủ đã chế biến): mỗi dòng 1 CHỦNG LOẠI, cùng khuôn với dòng tiêu
     thụ — loại tiền + tỷ giá nằm NGAY TRÊN DÒNG. Tiền quy về BASE = đồng (VND). */

import { type Bound, PRICE_CUP, PRICE_LACE, PRICE_LATEX } from "./entry-bounds";
import { CUP_PRICE_UNIT, LACE_PRICE_UNIT, LATEX_PRICE_UNIT } from "./purchase-price-unit";
import { GRADES, type Ccy, lineRevenueVnd } from "./unit-daily-consumption";

/** 1 dòng CHỦNG LOẠI của mủ nguyên liệu (chốt 20/09/2026): chủng loại · sản lượng TẤN QUY KHÔ.
 *  Không có đơn giá — đơn giá vẫn là MỘT ô cho cả loại mủ trong ngày (kho "Giá mủ nguyên liệu"). */
export type MaterialGradeLine = { grade: string; qty: number | null };

/** Một loại mủ nguyên liệu trên biểu Thu mua — gom mọi khoá payload + nhãn + biên cảnh báo về
 *  MỘT chỗ để 3 loại mủ không phải chép lại 3 lần (form · cảnh báo đều đọc từ đây).
 *
 *  ⚠ `table` / `total` PHẢI khớp `MATERIAL_GRADE_TABLES` ở backend
 *  (apps/api/app/services/unit_daily_fields.py): có bảng thì SERVER tự cộng ô tổng từ các dòng. */
export type Material = {
  key: "latex" | "cup" | "lace";  // khoá kho giá (`UnitPurchasePrice` · `PriceDraft`)
  label: string;
  table: string;        // bảng chủng loại trong payload
  total: string;        // ô tổng sản lượng (tấn quy khô)
  localKey: string;     // ô đơn giá theo nội tệ (đơn vị nước ngoài)
  vndKey: string;       // ô đơn giá VND (đơn vị trong nước)
  noPriceFlag: string;  // cờ "ngày đó không có đơn giá" (người dùng gõ 0)
  priceUnit: string;    // nhãn đơn vị của đơn giá VND
  degree: string;       // cơ sở tính độ (TSC/DRC) — dùng cho nhãn đơn giá nội tệ
  priceBound: Bound;    // biên cảnh báo của đơn giá VND
};

/** 3 loại mủ nguyên liệu, ĐÚNG THỨ TỰ hiện trên form (mủ dây chốt 28/08/2026, đặt cuối). */
export const MATERIALS: Material[] = [
  { key: "latex", label: "Mủ nước", table: "latex_grades", total: "latex_wet",
    localKey: "price_latex_local", vndKey: "price_latex_vnd", noPriceFlag: "no_price_latex",
    priceUnit: LATEX_PRICE_UNIT, degree: "độ TSC", priceBound: PRICE_LATEX },
  { key: "cup", label: "Mủ chén", table: "cup_grades", total: "coagulum",
    localKey: "price_cup_local", vndKey: "price_cup_vnd", noPriceFlag: "no_price_cup",
    priceUnit: CUP_PRICE_UNIT, degree: "độ DRC", priceBound: PRICE_CUP },
  { key: "lace", label: "Mủ dây", table: "lace_grades", total: "lace",
    localKey: "price_lace_local", vndKey: "price_lace_vnd", noPriceFlag: "no_price_lace",
    priceUnit: LACE_PRICE_UNIT, degree: "độ DRC", priceBound: PRICE_LACE },
];

/** Dòng chủng loại rỗng — mặc định chủng loại ĐẦU danh mục (giống bảng tồn kho/thành phẩm) để
 *  không bao giờ có dòng thiếu chủng loại: server BỎ những dòng như vậy, người nhập mất số mà
 *  không biết vì sao. */
export const emptyMaterialGradeLine = (): MaterialGradeLine => ({ grade: GRADES[0], qty: null });

/** Dòng ĐƯỢC TÍNH. Server bỏ dòng thiếu chủng loại hoặc thiếu sản lượng (`_clean_grade_qty`) và
 *  chỉ ghi đè ô tổng khi CÒN dòng — web phải đếm y hệt. Nếu không: vừa bấm "Tách chủng loại" (dòng
 *  trống) là ô tổng về 0, lưu phát nữa là mất luôn số tổng cũ của ngày đó. */
export const countedGradeRows = (rows: MaterialGradeLine[] | undefined): MaterialGradeLine[] =>
  (rows ?? []).filter((r) => (r.grade ?? "").trim() !== "" && r.qty != null);

/** Tổng sản lượng (tấn quy khô) của một bảng chủng loại — chính là số server ghi vào ô tổng. */
export const gradeQtyTotal = (rows: MaterialGradeLine[] | undefined): number =>
  countedGradeRows(rows).reduce((a, r) => a + (r.qty ?? 0), 0);

/** 1 dòng thu mua thành phẩm. `price` theo `ccy`: VND → triệu đ/tấn · USD → USD/tấn. */
export type FinishedLine = {
  grade: string;            // chủng loại (SVR CV 50, SVR 3L…)
  qty: number | null;       // sản lượng thu mua (tấn)
  price: number | null;     // đơn giá thu mua
  ccy?: Ccy;                // loại tiền của DÒNG này
  fx?: number | null;       // tỷ giá USD→VND của dòng này (chỉ cần khi ccy = USD)
};

/** Dòng rỗng cho nút "Thêm chủng loại". */
export const emptyFinishedLine = (): FinishedLine => ({
  grade: GRADES[0], qty: null, price: null, ccy: "VND", fx: null,
});

/** Giá trị 1 dòng quy về đồng — dùng chung công thức với dòng bán (thiếu tỷ giá USD → null). */
export const finishedLineVnd = (ln: FinishedLine): number | null => lineRevenueVnd(ln);

export type FinishedTotals = {
  qty: number;                   // tổng sản lượng (tấn)
  valueVnd: number;              // tổng giá trị (đồng)
  avgPriceTrieu: number | null;  // đơn giá BQ (triệu đ/tấn) = giá trị ÷ sản lượng
};

/** Cộng tổng bảng thu mua thành phẩm (sản lượng · giá trị · đơn giá bình quân). */
export function finishedTotals(rows: FinishedLine[] | undefined): FinishedTotals {
  let qty = 0, valueVnd = 0;
  for (const ln of rows ?? []) {
    qty += ln.qty ?? 0;
    valueVnd += finishedLineVnd(ln) ?? 0;
  }
  return { qty, valueVnd, avgPriceTrieu: qty > 0 ? valueVnd / qty / 1_000_000 : null };
}
