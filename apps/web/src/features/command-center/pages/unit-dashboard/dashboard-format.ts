/* Định dạng số / nhãn thời gian dùng chung cho màn Dashboard đơn vị.
   null = CHƯA CÓ SỐ → luôn hiện "—", không bao giờ quy về 0. */

import { dmy } from "../../../../lib/date";

type Num = number | null | undefined;

const vi = (v: number, digits: number) =>
  v.toLocaleString("vi-VN", { minimumFractionDigits: digits, maximumFractionDigits: digits });

/** Số chung với số lẻ cố định. */
export const fmtNum = (v: Num, digits = 0): string => (v == null ? "—" : vi(v, digits));

/** Tấn: 1 số lẻ khi dưới 100 tấn (số nhỏ mà cắt lẻ thì mất nghĩa), còn lại số nguyên. */
export const fmtTon = (v: Num): string => (v == null ? "—" : vi(v, Math.abs(v) < 100 ? 1 : 0));

/** Tỷ đồng: 2 số lẻ. */
export const fmtTy = (v: Num): string => fmtNum(v, 2);

/** Phần trăm: 1 số lẻ, kèm dấu %. */
export const fmtPct = (v: Num): string => (v == null ? "—" : `${vi(v, 1)}%`);

/** Ghép đơn vị sau số — chưa có số thì chỉ "—" (không "— tấn"). */
export const withUnit = (text: string, unit: string): string => (text === "—" ? text : `${text} ${unit}`);

/** Số lẻ của một mức giá theo ĐƠN VỊ: giá đ/độ, đ/kg… để nguyên số; riêng "triệu đ/tấn" giữ 2 số
 *  lẻ (45,41 triệu mà cắt còn 45 là lệch cả trăm nghìn đồng mỗi tấn — các màn khác cũng để 2 số lẻ). */
export const priceDigits = (unit: string): number => (/triệu/i.test(unit) ? 2 : 0);

export const fmtPrice = (v: Num, unit: string): string => fmtNum(v, priceDigits(unit));

/** Số lẻ theo đơn vị tính bất kỳ mà server gửi kèm (chỉ tiêu năm: tấn · tỷ đồng · …). */
export function fmtByUnit(v: Num, unit: string): string {
  if (/tỷ/i.test(unit)) return fmtTy(v);
  if (/tấn/i.test(unit) && !/\//.test(unit)) return fmtTon(v);
  return fmtPrice(v, unit);
}

/** Chậm hơn tiến độ thời gian quá ngưỡng này (điểm %) thì tô cảnh báo. */
const BEHIND_PP = 10;

/** % hoàn thành chỉ tiêu thấp hơn rõ rệt so với % thời gian đã qua của năm. */
export const isBehind = (pct: Num, timePct: number): boolean =>
  pct != null && pct < timePct - BEHIND_PP;

/** Nhãn một mốc của chuỗi: ngày → DD/MM/YYYY · tháng (YYYY-MM) → MM/YYYY. */
export function bucketLabel(asOf: string): string {
  if (asOf.length === 7) {
    const [y, m] = asOf.split("-");
    return `${m}/${y}`;
  }
  return dmy(asOf);
}

/** Sắp giảm dần theo một chỉ số; dòng chưa có số (null) xuống cuối, giữ nguyên thứ tự gốc. */
export function sortDesc<T>(rows: T[], get: (r: T) => Num): T[] {
  return [...rows].sort((a, b) => {
    const x = get(a), y = get(b);
    if (x == null) return y == null ? 0 : 1;
    if (y == null) return -1;
    return y - x;
  });
}
