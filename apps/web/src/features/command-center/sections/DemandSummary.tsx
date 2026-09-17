import { Tag } from "antd";
import { useMemo } from "react";

import type { DemandItem, DemandQtyUnit } from "../../../lib/market-demand-client";
import { DEMAND_STATUSES, fmtQty } from "../../../lib/market-demand-meta";

/** Dải tổng hợp nhỏ theo tình trạng của các phiếu đang hiện: "Đang đàm phán: 4 phiếu · 350 tấn".
 *  Tấn và container không cộng lẫn — container ghi riêng khi có. */
export default function DemandSummary({ items }: { items: DemandItem[] }) {
  const rows = useMemo(() => DEMAND_STATUSES.map((s) => {
    const list = items.filter((i) => i.status === s.value);
    // Làm tròn 1 chữ số lẻ: tổng cộng nhiều phiếu lẻ tới phần nghìn tấn ("2.396,425") khó đọc.
    const sum = (unit: DemandQtyUnit) => Math.round(
      list.reduce((t, i) => t + (i.qty_unit === unit && i.qty != null ? i.qty : 0), 0) * 10) / 10;
    return { ...s, count: list.length, tons: sum("ton"), containers: sum("container") };
  }), [items]);

  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
      {rows.map((r) => (
        <Tag key={r.value} color={r.color} style={{ fontSize: 13, padding: "3px 10px", margin: 0 }}>
          <b>{r.label}</b>: {r.count} phiếu
          {r.tons > 0 && ` · ${fmtQty({ qty: r.tons, qty_unit: "ton" })}`}
          {r.containers > 0 && ` · ${fmtQty({ qty: r.containers, qty_unit: "container" })}`}
        </Tag>
      ))}
    </div>
  );
}
