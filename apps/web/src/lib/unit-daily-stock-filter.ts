/* Lọc lưới TỒN KHO theo CHỦNG LOẠI (màn "Báo cáo tồn kho" → Tổng hợp toàn đơn vị).

   Tồn kho khối 1 & khối 2 vốn khai thành bảng theo từng chủng loại, còn "đã ký HĐ chưa giao" do
   hệ thống tính ra cũng kèm `by_grade` — nên lọc được ngay tại máy, không phải gọi lại server.
   Các cột tổng của lưới đều SUY RA từ mấy mảng này (xem `unit-daily-fields.COLUMNS`), nên cắt bớt
   dòng trong mảng là mọi cột tự tính lại đúng theo chủng loại đang chọn. */

import type { DayData } from "./unit-daily-client";

/** 2 bảng tồn kho nhập tay — nguồn của các cột "chưa nhập kho / đã nhập kho / tồn thành phẩm". */
const STOCK_BLOCKS = ["stock_not_warehoused", "stock_warehoused"] as const;

type GradeRow = { grade?: string; qty?: number | null };
type Signed = { qty?: number; by_grade?: Record<string, number> };

const rowsOf = (fields: Record<string, unknown>, key: string): GradeRow[] =>
  (Array.isArray(fields[key]) ? (fields[key] as GradeRow[]) : []);

/** Các chủng loại THỰC SỰ có trong số liệu của ngày đang xem (đã bỏ trùng, sắp xếp). */
export function gradesOf(day: DayData | null): string[] {
  if (!day) return [];
  const found = new Set<string>();
  for (const entry of Object.values(day.entries ?? {})) {
    const fields = (entry?.fields ?? {}) as Record<string, unknown>;
    for (const block of STOCK_BLOCKS) {
      for (const r of rowsOf(fields, block)) if (r.grade) found.add(r.grade);
    }
    const signed = fields.stock_signed_undelivered as Signed | undefined;
    for (const g of Object.keys(signed?.by_grade ?? {})) if (g) found.add(g);
  }
  return [...found].sort((a, b) => a.localeCompare(b, "vi"));
}

/** Bản sao của `day` chỉ giữ các chủng loại được chọn. Danh sách rỗng = không lọc (giữ nguyên). */
export function filterDayByGrades(day: DayData | null, grades: string[]): DayData | null {
  if (!day || !grades.length) return day;
  const keep = new Set(grades);
  const entries: DayData["entries"] = {};
  for (const [company, entry] of Object.entries(day.entries ?? {})) {
    if (!entry) continue;
    const fields = { ...(entry.fields ?? {}) } as Record<string, unknown>;
    for (const block of STOCK_BLOCKS) {
      fields[block] = rowsOf(fields, block).filter((r) => keep.has(r.grade ?? ""));
    }
    const signed = fields.stock_signed_undelivered as Signed | undefined;
    if (signed?.by_grade) {
      const byGrade = Object.fromEntries(
        Object.entries(signed.by_grade).filter(([g]) => keep.has(g)));
      // `qty` là số hiển thị ở cột "Đã ký HĐ chưa giao" → phải cộng lại theo đúng phần đã lọc,
      // giữ nguyên tổng cũ là cột này không khớp với các cột tồn kho bên cạnh.
      fields.stock_signed_undelivered = {
        ...signed,
        by_grade: byGrade,
        qty: Object.values(byGrade).reduce((a, q) => a + (q ?? 0), 0),
      };
    }
    entries[company] = { ...entry, fields: fields as typeof entry.fields };
  }
  return { ...day, entries };
}
