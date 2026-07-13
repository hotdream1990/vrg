/* Cảnh báo nhập tay: khi giá trị MỚI lệch ≥ ngưỡng so với GIÁ CŨ (kỳ trước) → nghi nhập sai.
   Chỉ so khi có đủ cả 2 số (bỏ qua khi chưa nhập / chưa có kỳ trước / kỳ trước = 0). */

/** Ngưỡng cảnh báo mặc định: lệch ≥ 10% so với kỳ trước. */
export const WARN_THRESHOLD = 0.1;

/** true nếu `current` lệch ≥ `threshold` so với `prev`. Thiếu 1 trong 2 hoặc prev=0 → false. */
export function isBigChange(
  current: number | null | undefined,
  prev: number | null | undefined,
  threshold = WARN_THRESHOLD,
): boolean {
  if (current == null || prev == null || prev === 0) return false;
  return Math.abs(current - prev) / Math.abs(prev) >= threshold;
}

/** Nhãn % thay đổi cho tooltip, vd "+12,5%" / "-15%". */
export function changeLabel(current: number, prev: number): string {
  const pct = ((current - prev) / prev) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%`;
}

/** Lưới (cột × ngày): trả prev[col][date] = giá gần nhất TRƯỚC `date` của cùng cột (bỏ ô trống). */
export function buildGridPrevMap(
  cols: string[],
  datesDesc: string[],
  values: Record<string, Record<string, number | null | undefined>> | undefined,
): Record<string, Record<string, number | null>> {
  const asc = [...datesDesc].sort(); // cũ → mới
  const out: Record<string, Record<string, number | null>> = {};
  for (const c of cols) {
    let last: number | null = null;
    const m: Record<string, number | null> = {};
    for (const d of asc) {
      m[d] = last; // prev = giá của ngày có số gần nhất trước d
      const cur = values?.[c]?.[d];
      if (cur != null) last = cur;
    }
    out[c] = m;
  }
  return out;
}
