/* Nguồn tiêu thụ theo TỪNG DÒNG chủng loại (05/10/2026): khai thác · thu mua · hàng hóa cao su.
   Dùng chung cho form, bảng đợt giao, màn chi tiết và các hộp chọn nguồn — một luật đọc nguồn duy
   nhất, khớp `calc.line_source` ở server. */

import type { ContractLine } from "../../../../lib/sales-contract-client";

/** Thứ tự hiện nguồn — cố định, để "Khai thác · Thu mua" không lúc này lúc kia đảo chỗ. */
const SOURCE_ORDER = ["exploit", "purchase", "goods"];
/** Lần giao nhập trước khi có ô nguồn được tính là khai thác (server làm đúng vậy). */
const DEFAULT_SOURCE = "exploit";

type HasSource = Pick<ContractLine, "source">;

/** Nguồn ĐÃ KHAI của dòng, không đoán: nguồn của dòng → nguồn chung của bản ghi (dữ liệu trước
 *  05/10/2026 chỉ có ô này) → null. */
export const knownLineSource = (line: HasSource, rowSource?: string | null): string | null =>
  line.source || rowSource || null;

/** Nguồn HIỆU LỰC của dòng ở một lần giao đã giao: như trên, cả hai trống thì là khai thác. */
export const effectiveLineSource = (line: HasSource, rowSource?: string | null): string =>
  knownLineSource(line, rowSource) ?? DEFAULT_SOURCE;

/** Các nguồn KHÁC NHAU của bản ghi, nối " · " theo thứ tự khai thác → thu mua → hàng hóa. Rỗng = "—".
 *  `delivered = false` (lần giao chưa có ngày giao): chỉ kể nguồn đã chọn — chưa giao mà ghi
 *  "Khai thác" là khai hộ một thứ đơn vị chưa chọn. */
export function sourceSummary(
  lines: HasSource[], rowSource: string | null | undefined,
  labels: Record<string, string> | undefined, delivered = true,
): string {
  const used = new Set(lines
    .map((ln) => (delivered ? effectiveLineSource(ln, rowSource) : knownLineSource(ln, rowSource)))
    .filter((s): s is string => !!s));
  if (!used.size) return "—";
  const rank = (s: string) => {
    const i = SOURCE_ORDER.indexOf(s);
    return i < 0 ? SOURCE_ORDER.length : i;
  };
  return [...used].sort((a, b) => rank(a) - rank(b))
    .map((s) => labels?.[s] ?? s).join(" · ");
}
