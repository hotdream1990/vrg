/* Dựng cột số liệu (nhóm theo Excel, cột suy ra xen giữa) DÙNG CHUNG cho bảng Tổng hợp và
   bảng Danh sách theo ngày. Mỗi dòng cần có { fields, company } để tính giá trị + tra chỉ tiêu KH. */

import type { ColumnsType } from "antd/es/table";

import type { UnitPurchasePrice } from "./unit-daily-client";
import { type Column, type Kind, type Values, colValue, displayDigits, fmtNum, segments, toDisplay } from "./unit-daily-fields";

/** Khối 3 (đã ký HĐ chưa giao) là phần NẰM TRONG tồn kho thành phẩm nên KHÔNG thể lớn hơn nó
    (yêu cầu C4 của khách). Vượt = số liệu sai ở đâu đó → tô cảnh báo để đơn vị soát lại.
    Kiểm ở cột thay vì ở form nhập, vì khối 3 nay là số hệ thống tự tính từ hợp đồng. */
const overCommitted = (kind: Kind, key: string, fields: Values): boolean => {
  if (kind !== "consumption" || key !== "stock_signed_t") return false;
  const signed = colValue(kind, "stock_signed_t", fields);
  const finished = colValue(kind, "stock_finished_t", fields);
  return signed != null && finished != null && signed > finished;
};

type Rowish = { fields: Values; company: string; prices?: UnitPurchasePrice };

/** Cột nhóm theo THỨ TỰ EXCEL (header gộp; cột suy ra tự tính; cột đơn giá link lấy từ `row.prices`). */
export function dataColumns<T extends Rowish>(kind: Kind, plans: Record<string, number>): ColumnsType<T> {
  const leaf = (c: Column) => ({
    title: `${c.label} (${c.unit})`,
    key: c.key,
    align: "right" as const,
    width: 118,
    render: (_: unknown, r: T) => {
      if (c.linked) return fmtNum(r.prices?.[c.linked] ?? null, 0);
      const text = fmtNum(toDisplay(c, colValue(kind, c.key, r.fields, plans[r.company])),
                          displayDigits(c.unit));
      if (!overCommitted(kind, c.key, r.fields)) return text;
      return (
        <span className="chip warn"
          title="Đã ký HĐ chưa giao đang LỚN HƠN tồn kho thành phẩm. Đây là phần nằm trong tồn kho nên không thể vượt quá — soát lại tồn kho khối 1, 2 và các hợp đồng.">
          {text}
        </span>
      );
    },
  });
  return segments(kind).map((seg) =>
    seg.group ? { title: seg.group, children: seg.cols.map(leaf) } : leaf(seg.cols[0]),
  );
}
