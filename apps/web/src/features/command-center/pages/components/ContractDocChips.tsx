import { PaperClipOutlined } from "@ant-design/icons";

import type { Contract } from "../../../../lib/sales-contract-client";

type Chip = { key: string; label: string; title: string; has: boolean };

/** Hợp đồng đã đính kèm đủ chứng từ chưa — để Ban rà nhanh đơn vị nào còn thiếu scan (07/10/2026).
 *
 *  Thanh toán chỉ xét ở hợp đồng GIAO 1 LẦN đã giao: giao nhiều lần thì thanh toán nằm ở từng đợt
 *  giao (danh sách không tải đợt), còn hợp đồng chưa giao thì chưa tới lúc thanh toán. */
export default function ContractDocChips({ c }: { c: Contract }) {
  const chips: Chip[] = [
    { key: "hd", label: "HĐ", title: "scan hợp đồng", has: c.files.length > 0 },
    { key: "coc", label: "Cọc", title: "chứng từ cọc", has: (c.deposits ?? []).some((d) => d.docs.length > 0) },
  ];
  // Chỉ thị giao hàng thuộc từng chuyến — chỉ xét ở hợp đồng giao 1 lần (đợt giao xem trong hợp đồng).
  if (c.delivery_type === "single") {
    chips.push({ key: "ct", label: "Chỉ thị", title: "chỉ thị giao hàng",
                 has: (c.instruction_docs ?? []).length > 0 });
  }
  if (c.delivery_type === "single" && c.delivered_at) {
    chips.push({ key: "tt", label: "TT", title: "chứng từ thanh toán", has: c.payment_docs.length > 0 });
  }
  return (
    <span style={{ display: "inline-flex", gap: 4 }}>
      {chips.map((k) => (k.has
        ? <span key={k.key} className="chip info" title={`Đã đính kèm ${k.title}`}>
            <PaperClipOutlined /> {k.label}
          </span>
        : <span key={k.key} className="chip" title={`Chưa đính kèm ${k.title}`}
            style={{ opacity: 0.55, textDecoration: "line-through" }}>{k.label}</span>))}
    </span>
  );
}
