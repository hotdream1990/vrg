/* Lũy kế theo khoảng đang xem cho biểu THU MUA — công cụ ĐỐI CHIẾU (chỉ đọc, không đổi mô hình nhập).
   Cột sản lượng/doanh thu = CỘNG dồn; cột đơn giá = BÌNH QUÂN GIA QUYỀN theo sản lượng
   (đúng quy tắc báo cáo kỳ). Chỉ dùng cho kind='purchase' — mọi cột là dòng chảy/đơn giá, không
   có chỉ tiêu THỜI ĐIỂM (tồn kho) nên cộng dồn không bị tính trùng. */

import type { TimelineRow } from "./unit-daily-client";
import { COLUMNS, type Kind, colValue, isSummable, toDisplay } from "./unit-daily-fields";

/** Cột đơn giá (bình quân) → cột SẢN LƯỢNG dùng làm trọng số khi bình quân gia quyền. */
const PRICE_WEIGHT: Record<string, string> = {
  price_latex: "latex_wet",
  price_cup: "coagulum",
  cup_raw_price: "cup_raw",
  rss_pressed_price: "rss_pressed",
  finished_price_avg: "finished_qty",
  price_avg: "consumption",
};

export type ColTotal = { display: number | null; mode: "sum" | "avg" | "none" };

/** Giá trị BASE 1 cột của 1 dòng — đơn giá LINK lấy từ row.prices, còn lại dùng colValue. */
function baseVal(kind: Kind, key: string, row: TimelineRow): number | null {
  const c = COLUMNS[kind].find((x) => x.key === key);
  if (!c) return null;
  if (c.linked) return row.prices?.[c.linked] ?? null;
  return colValue(kind, key, row.fields);
}

/** Tổng hợp cả khoảng: cột sản lượng/doanh thu = cộng; cột đơn giá = bình quân gia quyền theo SL. */
export function timelineTotals(kind: Kind, rows: TimelineRow[]): Record<string, ColTotal> {
  const out: Record<string, ColTotal> = {};
  for (const c of COLUMNS[kind]) {
    if (isSummable(c.unit)) {
      let sum = 0, any = false;
      for (const r of rows) {
        const v = baseVal(kind, c.key, r);
        if (v != null) { sum += v; any = true; }
      }
      out[c.key] = { display: any ? toDisplay(c, sum) : null, mode: "sum" };
    } else if (PRICE_WEIGHT[c.key]) {
      const wKey = PRICE_WEIGHT[c.key];
      let num = 0, den = 0;
      for (const r of rows) {
        const p = baseVal(kind, c.key, r);
        const w = colValue(kind, wKey, r.fields);
        if (p != null && w != null && w > 0) { num += p * w; den += w; }
      }
      out[c.key] = { display: den > 0 ? toDisplay(c, num / den) : null, mode: "avg" };
    } else {
      out[c.key] = { display: null, mode: "none" };
    }
  }
  return out;
}
