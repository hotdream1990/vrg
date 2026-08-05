/* Dựng cột số liệu (nhóm theo Excel, cột suy ra xen giữa) DÙNG CHUNG cho bảng Tổng hợp và
   bảng Danh sách theo ngày. Mỗi dòng cần có { fields, company } để tính giá trị + tra chỉ tiêu KH. */

import type { ColumnsType } from "antd/es/table";

import type { UnitPurchasePrice } from "./unit-daily-client";
import { type Column, type Kind, type Values, colValue, displayDigits, fmtNum, segments, toDisplay } from "./unit-daily-fields";

/* ĐÃ BỎ cảnh báo "khối 3 > tồn kho thành phẩm" (05/08/2026). Cảnh báo đó dựa trên cách tính cũ:
   khối 3 chỉ gồm các đợt đã gom hàng vào kho nên không thể vượt tồn kho. Nay khối 3 = sản lượng
   HỢP ĐỒNG − đã giao, tính từ ngày ký, nên phần hàng CHƯA SẢN XUẤT cũng nằm trong đó → vượt tồn
   kho thành phẩm là chuyện bình thường. Giữ lại thì cảnh báo đỏ hiện gần như mọi dòng, người dùng
   quen mắt rồi bỏ qua cả những cảnh báo thật. */

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
      return fmtNum(toDisplay(c, colValue(kind, c.key, r.fields, plans[r.company])),
                    displayDigits(c.unit));
    },
  });
  return segments(kind).map((seg) =>
    seg.group ? { title: seg.group, children: seg.cols.map(leaf) } : leaf(seg.cols[0]),
  );
}
