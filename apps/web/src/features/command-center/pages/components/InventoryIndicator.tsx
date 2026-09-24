import { ArrowDownOutlined, ArrowUpOutlined, InboxOutlined } from "@ant-design/icons";

import { dmy } from "../../../../lib/date";
import { LEAN_LABEL, leanMoves } from "../../../../lib/floor-rationale";
import type { InventoryAt, InventoryLean } from "../../../../lib/floor-suggest-client";

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

/** Tồn kho Tập đoàn THEO NGÀY (cộng từ biểu Tồn kho đơn vị) — bối cảnh cho đề xuất điều chỉnh. */
export default function InventoryIndicator({ inv, lean, start }: {
  inv?: InventoryAt | null; lean?: InventoryLean | null; start?: string;
}) {
  if (!inv) {
    return start ? (
      <div className="card" style={{ fontSize: 13, color: "var(--muted)" }}>
        <InboxOutlined /> Chưa có số tồn kho cho ngày này — tồn kho theo ngày của đơn vị có từ {dmy(start)}.
      </div>
    ) : null;
  }
  // Thay đổi chỉ tính trên đơn vị có số ở cả 2 ngày → có thể khác hiệu của 2 con số tổng.
  const compare = inv.base_day
    ? `Thay đổi so với ${dmy(inv.base_day)} (lần ban hành trước), tính trên ${inv.units_compared} đơn vị có số cả 2 ngày.`
    : "Chưa có mốc so sánh: lần ban hành trước chưa có tồn kho theo ngày.";
  const freeShare = inv.ton_kho ? Math.round((inv.ton_free / inv.ton_kho) * 100) : null;
  return (
    <div className="card" style={{ display: "flex", gap: 28, alignItems: "center", flexWrap: "wrap" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <InboxOutlined style={{ fontSize: 18 }} />
        <div>
          <b>Tồn kho Tập đoàn</b>
          <div style={{ fontSize: 12, color: "var(--muted)" }}>
            ngày {dmy(inv.day)} · {inv.units_counted} đơn vị có số
          </div>
        </div>
      </div>
      <Cell label="Tổng tồn kho" value={inv.ton_kho} d={inv.d_ton_kho} />
      <Cell label="Đã có hợp đồng" value={inv.ton_kho_hd} />
      <Cell label="Tự do (chưa có HĐ)" value={inv.ton_free} d={inv.d_free} />
      <div style={{ fontSize: 12, color: "var(--muted)", maxWidth: 280 }}>
        {freeShare != null && <div>Tự do chiếm {freeShare}% tồn kho — càng cao càng áp lực hạ sàn để dễ bán.</div>}
        <div>{compare}</div>
      </div>
      {lean && (
        <div style={{ flexBasis: "100%", fontSize: 13, padding: "6px 10px", borderRadius: 8,
          background: "var(--card-2, #f6faf7)" }}>
          <b>Tham chiếu điều chỉnh:</b> {LEAN_LABEL[lean.direction]} ({leanMoves(lean)}).
          <span style={{ color: "var(--muted)" }}> Chỉ để nghiêng lên/xuống, không đổi số của mô hình.</span>
        </div>
      )}
    </div>
  );
}
