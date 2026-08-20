/* Chọn MỐC ĐỌC cho chuỗi thu mua theo ngày (giá + sản lượng do đơn vị thành viên tự khai).

   Sản lượng một ngày là TỔNG của nhiều đơn vị, mà các đơn vị nhập rải rác trong ngày → ngày hôm
   nay/hôm qua gần như luôn thiếu đơn vị. Lấy thẳng ngày cuối chuỗi làm mốc so sánh thì "sản lượng
   giảm mạnh" chỉ là chưa ai nhập, không phải thị trường yếu đi.

   Quy tắc: mốc đọc = ngày MỚI NHẤT có độ phủ đạt ngưỡng so với ngày phủ tốt nhất trong cửa sổ.
   KHÔNG đắp số ngày khác vào ngày thiếu — chỉ chọn đúng ngày để đọc, và luôn nói rõ ngày nào. */

import type { PurchaseDayStat, PurchaseSeries } from "./api-client";

export type Material = "latex" | "cup";
type Row = PurchaseSeries["rows"][number];

/** Ngày đạt ngưỡng khi có ít nhất 60% số đơn vị của ngày phủ tốt nhất (cả giá lẫn sản lượng). */
const COVERAGE_RATIO = 0.6;

const hasAny = (r: Row, key: Material) => r[key].units > 0 || r[key].qty != null;

/** {settled: mốc đọc đủ số · latest: ngày mới nhất có số · thin: ngày mới hơn nhưng chưa đủ}. */
export function readAt(rows: Row[], key: Material): {
  settled: Row | null; prev: Row | null; latest: Row | null; thin: Row | null;
} {
  const maxUnits = Math.max(0, ...rows.map((r) => r[key].units));
  const maxQty = Math.max(0, ...rows.map((r) => r[key].qty_units));
  const full = rows.filter((r) => hasAny(r, key)
    && r[key].units >= maxUnits * COVERAGE_RATIO && r[key].qty_units >= maxQty * COVERAGE_RATIO);
  const latest = [...rows].reverse().find((r) => hasAny(r, key)) ?? null;
  const settled = full.at(-1) ?? latest;
  return {
    settled,
    prev: full.at(-1) === settled ? full.at(-2) ?? null : null,
    latest,
    thin: settled && latest && latest.as_of > settled.as_of ? latest : null,
  };
}

/** Câu nhắc "ngày mới hơn chưa đủ đơn vị khai" — để không ai đọc mốc đủ số thành số mới nhất. */
export const thinNote = (thin: Row | null, key: Material, dm: (v: string) => string): string =>
  thin ? ` Ngày ${dm(thin.as_of)} mới có ${Math.max(thin[key].units, thin[key].qty_units)} đơn vị khai — chưa đủ để so sánh.` : "";

export type { PurchaseDayStat, Row };
