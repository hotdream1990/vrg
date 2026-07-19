/* Dựng cột số liệu (nhóm theo Excel, cột suy ra xen giữa) DÙNG CHUNG cho bảng Tổng hợp và
   bảng Danh sách theo ngày. Mỗi dòng cần có { fields, company } để tính giá trị + tra chỉ tiêu KH. */

import type { ColumnsType } from "antd/es/table";

import type { UnitPurchasePrice } from "./unit-daily-client";
import { type Column, type Kind, type Values, colValue, fmtNum, segments, toDisplay } from "./unit-daily-fields";

type Rowish = { fields: Values; company: string; prices?: UnitPurchasePrice };

/** Cột nhóm theo THỨ TỰ EXCEL (header gộp; cột suy ra tự tính; cột đơn giá link lấy từ `row.prices`). */
export function dataColumns<T extends Rowish>(kind: Kind, plans: Record<string, number>): ColumnsType<T> {
  const leaf = (c: Column) => ({
    title: `${c.label} (${c.unit})`,
    key: c.key,
    align: "right" as const,
    width: 118,
    render: (_: unknown, r: T) =>
      c.linked
        ? fmtNum(r.prices?.[c.linked] ?? null, 0)
        : fmtNum(toDisplay(c, colValue(kind, c.key, r.fields, plans[r.company])), c.unit === "%" ? 1 : 2),
  });
  return segments(kind).map((seg) =>
    seg.group ? { title: seg.group, children: seg.cols.map(leaf) } : leaf(seg.cols[0]),
  );
}
