/* Thu mua THÀNH PHẨM (mua lại mủ đã chế biến) — nhập theo BẢNG NHIỀU DÒNG, mỗi dòng 1 CHỦNG LOẠI.
   Cùng khuôn với dòng tiêu thụ: loại tiền + tỷ giá nằm NGAY TRÊN DÒNG (một ngày có thể mua chủng
   loại này bằng VNĐ, chủng loại kia bằng USD). Tiền quy về BASE = đồng (VND). */

import { GRADES, type Ccy, lineRevenueVnd } from "./unit-daily-consumption";

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
