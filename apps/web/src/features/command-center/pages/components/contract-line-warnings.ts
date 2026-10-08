/* Cảnh báo từng ô của DÒNG HỢP ĐỒNG BÁN (viền vàng + danh sách "ô cần kiểm tra lại" ở form).
   Tách khỏi `ContractLinesTable` để bảng chỉ lo bố cục. */

import {
  FX_USD_VND, TONNES_CONTRACT, boundWarning, fxWarning, priceBound,
} from "../../../../lib/entry-bounds";
import {
  REVENUE_MAX_RATIO, REVENUE_WARN_RATIO, computedLineRevenueVnd, fmtDong, revenueOverrideAllowed,
  revenueOverrideDiff,
} from "../../../../lib/contract-money";
import type { ContractLine } from "../../../../lib/sales-contract-client";

const pct = (r: number) => (r * 100).toLocaleString("vi-VN", { maximumFractionDigits: 1 });

/** Doanh thu VNĐ kế toán so với thành tiền × tỷ giá: lệch quá 2% thì nhắc, quá 10% thì báo luôn là
 *  không lưu được (form chặn ở `problems()`, server cũng chặn) — nói ngay tại ô cho người nhập biết
 *  sửa ở đâu. Hay gặp nhất là gõ TRIỆU đồng vào ô tính bằng ĐỒNG (lệch ~100%). */
function revenueWarning(ln: ContractLine, requireFx: boolean): string | null {
  if (!revenueOverrideAllowed(ln, requireFx) || ln.revenue_vnd == null) return null;
  if (ln.revenue_vnd <= 0) return "Phải lớn hơn 0 — để trống thì phần mềm tự tính.";
  const diff = revenueOverrideDiff(ln);
  if (diff == null || diff <= REVENUE_WARN_RATIO) return null;
  const base = `Lệch ${pct(diff)}% so với thành tiền × tỷ giá `
    + `(${fmtDong(computedLineRevenueVnd(ln) as number)} đồng)`;
  return diff > REVENUE_MAX_RATIO
    ? `${base} — quá ${pct(REVENUE_MAX_RATIO)}% nên không lưu được, kiểm tra lại số (ô tính bằng đồng).`
    : `${base} — kiểm tra lại số.`;
}

/** Cảnh báo NHẦM ĐƠN VỊ TÍNH của một dòng — chìa khoá là ô đơn giá.
 *
 *  Vì sao phải có ở đây: rà production ngày 10/08/2026 thấy 47 dòng nhập đơn giá theo ĐỒNG/tấn
 *  (61.600.000) hoặc NGHÌN ĐỒNG/tấn (49.850) trong khi ô tính bằng TRIỆU ĐỒNG/tấn → doanh thu
 *  tiêu thụ bị thổi tới 8.748.352 tỷ đồng (số đúng ~1.065 tỷ). Bộ biên `entry-bounds` được dựng
 *  đúng cho lỗi này từ 07/2026 nhưng chỉ gắn ở biểu nhập ngày; khi tiêu thụ chuyển sang nhập ở
 *  hợp đồng (30/07/2026) thì màn mới KHÔNG có cảnh báo nào — lỗi cũ lặp lại y nguyên.
 *  CHỈ CẢNH BÁO, không chặn lưu: giá thị trường có thể vượt biên thật, chặn cứng là chặn nghiệp vụ.
 */
export function lineWarnings(ln: ContractLine, needDry: boolean, requireFx: boolean) {
  return {
    qty: boundWarning(ln.qty, TONNES_CONTRACT),
    qty_dry: needDry && !ln.qty_dry ? "Bắt buộc nhập quy khô mới lưu được." : null,
    price: boundWarning(ln.price, priceBound(ln.ccy)),
    // Chưa có ngày giao thì tỷ giá trống là BÌNH THƯỜNG, không phải ô cần kiểm tra — nhắc ở đây
    // sẽ hiện cảnh báo trên gần như mọi hợp đồng ngoại tệ mới ký.
    fx: (requireFx ? fxWarning(ln) : null) ?? boundWarning(ln.fx, FX_USD_VND),
    revenue_vnd: revenueWarning(ln, requireFx),
  };
}
