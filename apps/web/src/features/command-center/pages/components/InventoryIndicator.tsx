import { ArrowDownOutlined, ArrowUpOutlined, InboxOutlined } from "@ant-design/icons";

import type { InventoryAt } from "../../../../lib/floor-suggest-client";

const fmt = (n: number | null) => (n == null ? "—" : n.toLocaleString("vi-VN"));

/** Δ tồn kho: tăng = áp lực cung (đỏ), giảm = nhẹ áp lực (xanh). */
function Trend({ d }: { d: number | null }) {
  if (d == null) return null;
  const color = d > 0 ? "#e11d48" : d < 0 ? "#16a34a" : "var(--muted)";
  const Icon = d > 0 ? ArrowUpOutlined : ArrowDownOutlined;
  return (
    <span style={{ color, fontSize: 12, marginLeft: 4 }}>
      {d !== 0 && <Icon />} {d > 0 ? "+" : ""}{fmt(d)}
    </span>
  );
}

function Cell({ label, value, d }: { label: string; value: number | null; d?: number | null }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--muted)" }}>{label}</div>
      <div style={{ fontSize: 17, fontWeight: 700 }}>
        {fmt(value)} <span style={{ fontSize: 11, fontWeight: 400, color: "var(--muted)" }}>tấn</span>
        {d !== undefined && <Trend d={d} />}
      </div>
    </div>
  );
}

/** Chỉ số tồn kho Tập đoàn tại lần ban hành đang chọn (bối cảnh cho đề xuất điều chỉnh). */
export default function InventoryIndicator({ inv }: { inv?: InventoryAt | null }) {
  if (!inv) return null;
  return (
    <div className="card" style={{ display: "flex", gap: 28, alignItems: "center", flexWrap: "wrap" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <InboxOutlined style={{ fontSize: 18 }} />
        <div>
          <b>Tồn kho Tập đoàn</b>
          <div style={{ fontSize: 12, color: "var(--muted)" }}>tuần {inv.week}</div>
        </div>
      </div>
      <Cell label="Tổng tồn kho" value={inv.ton_kho} d={inv.d_ton_kho} />
      <Cell label="Đã có hợp đồng" value={inv.ton_kho_hd} />
      <Cell label="Tự do (chưa có HĐ)" value={inv.ton_free} d={inv.d_free} />
      {inv.ton_free != null && (
        <div style={{ fontSize: 12, color: "var(--muted)", maxWidth: 220 }}>
          {inv.ton_free < 0
            ? "Đã ký HĐ vượt tồn kho → nguồn chặt, hỗ trợ giữ/nâng sàn."
            : "Tồn tự do cao → áp lực hạ sàn để dễ bán."}
        </div>
      )}
    </div>
  );
}
