/* Tiền của DÒNG HỢP ĐỒNG BÁN — 1 nguồn duy nhất cho form nhập, màn chi tiết và ô đặt cọc.
   Luật làm tròn PHẢI khớp server (làm tròn nửa LÊN, không bao giờ kiểu "ngân hàng"): lệch một đồng
   là form cho lưu mà server chặn (hoặc ngược lại), và số trên màn khác số trên báo cáo. */

import type { ContractLine } from "./sales-contract-client";

/** Lệch giữa doanh thu kế toán và thành tiền × tỷ giá: quá mức này thì nhắc (vàng)… */
export const REVENUE_WARN_RATIO = 0.02;
/** …quá mức này thì CHẶN lưu — server cũng trả 400 với đúng ngưỡng này. */
export const REVENUE_MAX_RATIO = 0.1;

const TRIEU = 1_000_000;

export const isForeignCcy = (ccy: string | null | undefined): boolean => !!ccy && ccy !== "VND";

/** Số thập phân CHÍNH XÁC của một số đã nhập: "19.957" → {n: 19957n, s: 3}. null với số dạng mũ. */
function toDec(x: number): { n: bigint; s: number } | null {
  if (!Number.isFinite(x)) return null;
  const str = String(x);
  if (/e/i.test(str)) return null;
  const [int, frac = ""] = str.replace("-", "").split(".");
  const n = BigInt(int + frac);
  return { n: str.startsWith("-") ? -n : n, s: frac.length };
}

/** TÍCH các thừa số rồi làm tròn nửa LÊN (xa số 0) tới `digits` số lẻ — tính bằng số nguyên lớn trên
 *  đúng chuỗi số đã nhập, y như server làm bằng Decimal/numeric. Số thực máy tính mang "bụi":
 *  20,13 × 1.725,5 ra 34734,314999999995 → làm tròn thường cho ,31 trong khi đúng là ,315 → ,32; dòng
 *  doanh thu trên ~19 tỷ đồng thì bụi đủ lớn để lệch server 1 đồng. */
function roundProduct(factors: number[], digits: number): number {
  let n = BigInt(1);
  let s = 0;
  for (const f of factors) {
    const d = toDec(f);
    if (!d) return roundFloat(factors.reduce((a, b) => a * b, 1), digits);
    n *= d.n;
    s += d.s;
  }
  if (s <= digits) return Number(n) / 10 ** s;
  const neg = n < BigInt(0);
  const abs = neg ? -n : n;
  const div = BigInt(10) ** BigInt(s - digits);
  const q = abs / div + (((abs % div) * BigInt(2)) >= div ? BigInt(1) : BigInt(0));
  const out = Number(q) / 10 ** digits;
  return neg && out !== 0 ? -out : out;
}

/** Dự phòng cho số dạng mũ ("1e-7"): gọt bụi 15 chữ số có nghĩa rồi làm tròn. */
function roundFloat(x: number, digits: number): number {
  if (!Number.isFinite(x)) return x;
  const abs = Math.abs(Number(x.toPrecision(15)));
  const out = Math.round(abs * 10 ** digits) / 10 ** digits;
  return x < 0 && out !== 0 ? -out : out;
}

/** Làm tròn nửa LÊN (xa số 0) tới `digits` chữ số thập phân — không bao giờ kiểu "ngân hàng". */
export const roundHalfUp = (x: number, digits = 0): number => roundProduct([x], digits);

/** Thành tiền 1 dòng theo NGUYÊN TỆ của dòng: ngoại tệ làm tròn 2 số lẻ (như server) · VNĐ là
 *  triệu đồng, giữ nguyên SL × đơn giá. null khi thiếu SL hoặc đơn giá. */
export function lineAmount(ln: ContractLine): number | null {
  if (ln.qty == null || ln.price == null) return null;
  return isForeignCcy(ln.ccy) ? roundProduct([ln.qty, ln.price], 2) : ln.qty * ln.price;
}

/** Doanh thu VNĐ (ĐỒNG) phần mềm tự tính: VNĐ = SL × đơn giá × 1 triệu · ngoại tệ = thành tiền (đã
 *  làm tròn 2 số lẻ) × tỷ giá. null khi thiếu số — ngoại tệ chưa có tỷ giá thì KHÔNG coi là 0. */
export function computedLineRevenueVnd(ln: ContractLine): number | null {
  if (ln.qty == null || ln.price == null) return null;
  if (!isForeignCcy(ln.ccy)) return roundProduct([ln.qty, ln.price, TRIEU], 0);
  const amount = lineAmount(ln);
  return amount == null || !ln.fx ? null : roundProduct([amount, ln.fx], 0);
}

/** Doanh thu VNĐ dùng cho mọi phép cộng: dòng ngoại tệ có "Doanh thu VNĐ (kế toán)" thì lấy số đó
 *  (kế toán ghi một phần tiền theo tỷ giá ngày cọc nên SL × giá × MỘT tỷ giá không ra đúng số),
 *  không thì lấy số tự tính. */
export function lineRevenueVnd(ln: ContractLine): number | null {
  if (isForeignCcy(ln.ccy) && ln.revenue_vnd != null) return ln.revenue_vnd;
  return computedLineRevenueVnd(ln);
}

/** Dòng này có được mang doanh thu kế toán không — đúng lúc ô tỷ giá là bắt buộc: dòng ngoại tệ của
 *  bản ghi ĐÃ CÓ NGÀY GIAO. Ngoài trường hợp đó server trả 400. */
export const revenueOverrideAllowed = (ln: ContractLine, delivered: boolean): boolean =>
  delivered && isForeignCcy(ln.ccy);

/** Xoá doanh thu kế toán ở dòng không còn được mang nó (đổi sang VNĐ, bỏ ngày giao, đổi đơn vị) —
 *  ô đã ẩn nên người nhập không tự xoá được, giữ lại là server chặn mà không biết sửa ở đâu.
 *  Trả lại đúng mảng cũ khi không có gì phải xoá. */
export function clearInvalidRevenue(lines: ContractLine[], delivered: boolean): ContractLine[] {
  const bad = (l: ContractLine) => l.revenue_vnd != null && !revenueOverrideAllowed(l, delivered);
  return lines.some(bad) ? lines.map((l) => (bad(l) ? { ...l, revenue_vnd: null } : l)) : lines;
}

/** Tỷ lệ lệch |kế toán − tự tính| / tự tính. null khi không có số kế toán hoặc không so được
 *  (dòng VNĐ, thiếu tỷ giá, thành tiền 0). */
export function revenueOverrideDiff(ln: ContractLine): number | null {
  if (!isForeignCcy(ln.ccy) || ln.revenue_vnd == null) return null;
  const computed = computedLineRevenueVnd(ln);
  if (!computed) return null;
  return Math.abs(ln.revenue_vnd - computed) / computed;
}

/** Hiển thị tiền theo loại tiền: ngoại tệ LUÔN đúng 2 số lẻ (34.425,83) · VNĐ (triệu đồng) giữ 0–3
 *  số lẻ như các ô số khác. */
export function fmtCcyAmount(n: number, ccy: string | null | undefined): string {
  if (!isForeignCcy(ccy)) return n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });
  return roundHalfUp(n, 2).toLocaleString("vi-VN", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
}

/** Đồng chẵn kiểu vi-VN (1.234.567.890) — gợi ý trong ô doanh thu kế toán. */
export const fmtDong = (n: number): string => roundHalfUp(n, 0).toLocaleString("vi-VN");
