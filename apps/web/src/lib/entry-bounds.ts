/* Biên hợp lệ của các ô NHẬP TAY — CHỈ ĐỂ CẢNH BÁO, KHÔNG CHẶN LƯU.
 *
 *  Vì sao cần: ngày 23–24/07/2026 có 7 đơn vị nhập đơn giá theo ĐỒNG/tấn trong khi ô tính bằng
 *  TRIỆU đồng/tấn → doanh thu bị thổi gấp ~1 triệu lần và chảy thẳng vào báo cáo tổng hợp.
 *  Nhầm đơn vị tính là lỗi hay gặp nhất, và nó luôn lệch theo BỘI SỐ CỦA 10 → biên đặt RỘNG
 *  (≈2 lần biên dữ liệu thật) vẫn bắt được, mà không kêu oan lúc giá biến động mạnh.
 *
 *  Cách chỉnh: số dưới đây lấy từ dữ liệu thật trên production (2024→07/2026) rồi nới rộng.
 *  Khi thị trường đổi mặt bằng giá (vd giá bán vượt 150 triệu đ/tấn là bình thường) thì sửa
 *  Ở ĐÂY — đừng rải hằng số ra từng màn.
 */

import { formatViNumber } from "./number-format";

/** Khoảng giá trị thường gặp của một ô nhập. `lo`/`hi` bỏ trống = không chặn phía đó. */
export type Bound = { lo?: number; hi?: number; unit: string };

// ── Sản lượng (tấn) ──────────────────────────────────────────────────────────────────────
/** Số phát sinh trong MỘT NGÀY của MỘT đơn vị. Thực tế prod: 0–227 tấn (một ngoại lệ 5.719). */
export const TONNES_DAILY: Bound = { lo: 0, hi: 1_000, unit: "tấn" };
/** Tồn kho là số TẠI THỜI ĐIỂM (tích luỹ) nên cao hơn sản lượng ngày.
 *  Đo lại 10/08/2026: bản ghi ĐÚNG lớn nhất là 9.340 tấn (C.R.C.K.2) — mức 5.000 cũ kêu oan đơn vị
 *  này gần như MỖI NGÀY, và cảnh báo kêu mỗi ngày thì lần sai thật (7.701.258 tấn) cũng bị bỏ qua. */
export const TONNES_STOCK: Bound = { lo: 0, hi: 20_000, unit: "tấn" };
/** Sản lượng một DÒNG hợp đồng/đợt giao — là cam kết cả lô nên lớn hơn số phát sinh một ngày.
 *  Thực tế prod: 0,04–3.024 tấn (p99 = 630). */
export const TONNES_CONTRACT: Bound = { lo: 0, hi: 10_000, unit: "tấn" };
/** Chỉ tiêu CẢ NĂM — to thật, không được áp ngưỡng ngày. Thực tế prod: 10–14.500 tấn. */
export const TONNES_YEAR: Bound = { lo: 0, hi: 50_000, unit: "tấn" };
/** Sản lượng chuyển từ năm trước sang. Thực tế prod: 0–1.814 tấn. */
export const TONNES_CARRY: Bound = { lo: 0, hi: 20_000, unit: "tấn" };

// ── Giá bán / đơn giá thành phẩm — KHOÁ THEO LOẠI TIỀN CỦA DÒNG ──────────────────────────
// Bắt buộc tách theo loại tiền: cùng một lô mủ, giá VND ≈ 50 còn giá USD ≈ 1.900 — chênh 40 lần.
// Dùng chung một biên thì hoặc bỏ lọt lỗi VND, hoặc kêu oan mọi dòng USD.
/** Thực tế prod: 43,9–56,2 triệu đ/tấn. */
export const PRICE_VND: Bound = { lo: 10, hi: 150, unit: "triệu đ/tấn" };
/** Thực tế prod: ~1.880 USD/tấn (kho giá physical 1.267–3.253). */
export const PRICE_USD: Bound = { lo: 500, hi: 8_000, unit: "USD/tấn" };
/** Biên đơn giá theo loại tiền của DÒNG đang nhập.
    Nội tệ đơn vị nước ngoài (LAK/KHR) có mặt bằng số hoàn toàn khác (1 USD ≈ 21.000 LAK) và chưa
    đủ dữ liệu thật để chốt biên → trả biên RỖNG: thà không cảnh báo còn hơn kêu oan mọi dòng. */
export const priceBound = (ccy: string | undefined): Bound => {
  if (ccy === "USD") return PRICE_USD;
  if (ccy === "LAK" || ccy === "KHR") return { unit: `${ccy}/tấn` };
  return PRICE_VND;
};

// ── Tỷ giá & đơn giá mủ nguyên liệu ──────────────────────────────────────────────────────
/** Thực tế prod: 26.000–26.510. Biên rộng để còn dùng được nhiều năm. */
export const FX_USD_VND: Bound = { lo: 15_000, hi: 40_000, unit: "VND" };
/** Đơn giá mủ nước. Thực tế prod: 376–380 (kho giá thu mua 390–538). */
export const PRICE_LATEX: Bound = { lo: 100, hi: 1_500, unit: "đồng/độ TSC" };
/** Đơn giá mủ chén (tính theo độ TSC hoặc DRC). Thực tế prod: 82–345. */
export const PRICE_CUP: Bound = { lo: 50, hi: 1_500, unit: "đồng/độ" };
/** Doanh thu một ngày của một đơn vị. Thực tế prod (bản ghi đúng): ≤ 12 tỷ đồng. */
export const REVENUE_TY: Bound = { lo: 0, hi: 500, unit: "tỷ đồng" };

/** Lời cảnh báo cho một ô, hoặc null nếu số nằm trong khoảng. Không có số / không có biên → null.
 *
 *  Số 0 KHÔNG bị coi là "thấp hơn biên": mua 0 đồng là nghiệp vụ thật (nhận hàng bù chênh lệch
 *  thu mua), và biên dưới sinh ra để bắt NHẦM ĐƠN VỊ TÍNH — mà nhầm đơn vị luôn cho ra số lệch
 *  theo bội của 10 (0,0552 · 55.200.000), không bao giờ cho ra đúng 0. Cảnh báo ở đây là kêu oan,
 *  mà kêu oan mỗi ngày thì tới lúc sai thật người nhập cũng bỏ qua nốt.
 */
export function boundWarning(v: number | null | undefined, b?: Bound | null): string | null {
  if (v == null || b == null || Number.isNaN(v)) return null;
  if (b.hi != null && v > b.hi) {
    return `Vượt ${formatViNumber(b.hi)} ${b.unit} — kiểm tra lại đơn vị tính (ô này nhập theo ${b.unit}).`;
  }
  if (b.lo != null && v !== 0 && v < b.lo) {
    return `Thấp hơn ${formatViNumber(b.lo)} ${b.unit} — kiểm tra lại đơn vị tính (ô này nhập theo ${b.unit}).`;
  }
  return null;
}

/** Dòng chọn USD mà bỏ trống tỷ giá → doanh thu dòng đó KHÔNG được tính (xem `lineRevenueVnd`). */
export function fxWarning(line: { ccy?: string; fx?: number | null }): string | null {
  const ccy = line.ccy ?? "VND";
  if (ccy === "VND") return null;
  if (line.fx != null && line.fx !== 0) return null;
  return `Dòng chọn ${ccy} nhưng chưa nhập tỷ giá — doanh thu dòng này sẽ không được tính.`;
}
