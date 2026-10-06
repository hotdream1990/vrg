/* Nguồn tiêu thụ trên Dashboard đơn vị: khoá số server trả (`qty_exploit/purchase/goods`, tính theo
   TỪNG DÒNG chủng loại của lần giao) + nhãn + màu — dùng chung cho biểu đồ xu hướng (tách theo nguồn)
   và bảng cơ cấu nguồn × chủng loại. Vắng khoá = API cũ → ẩn mọi phần theo nguồn, không vẽ thành 0. */

import { SOURCE_LABELS } from "../components/consumption-source-labels";
import { type Num, fmtPct, share } from "./dashboard-format";

export type SourceQtyKey = "qty_exploit" | "qty_purchase" | "qty_goods";
export type SourceQtys = Partial<Record<SourceQtyKey, Num>>;

export const SOURCE_PARTS: { key: SourceQtyKey; label: string; color: string }[] = [
  { key: "qty_exploit", label: SOURCE_LABELS.exploit, color: "#16a34a" },
  { key: "qty_purchase", label: SOURCE_LABELS.purchase, color: "#f97316" },
  { key: "qty_goods", label: SOURCE_LABELS.goods, color: "#8b5cf6" },
];

/** Server có trả số theo nguồn không (API cũ thì cả 3 khoá đều vắng). */
export const hasSourceKeys = (q: SourceQtys): boolean => SOURCE_PARTS.some((p) => q[p.key] !== undefined);

/** Tổng 3 nguồn (bỏ ô chưa có số) — null khi cả 3 đều chưa có số. */
export function sourceSum(q: SourceQtys): number | null {
  const vals = SOURCE_PARTS.map((p) => q[p.key]).filter((v): v is number => v != null);
  return vals.length ? vals.reduce((a, v) => a + v, 0) : null;
}

/** "Khai thác 62,1% · Thu mua 30,4% · Hàng hóa cao su 7,5%" — null khi API cũ hoặc tổng bằng 0. */
export function sourceShareText(q: SourceQtys): string | null {
  const total = sourceSum(q);
  if (!hasSourceKeys(q) || total == null || total <= 0) return null;
  return SOURCE_PARTS.map((p) => `${p.label} ${fmtPct(share(q[p.key], total))}`).join(" · ");
}
