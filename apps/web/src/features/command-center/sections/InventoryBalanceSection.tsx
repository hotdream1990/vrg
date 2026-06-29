import { useEffect, useState } from "react";

import { type InventoryWeek, fetchInventory } from "../../../lib/inventory-client";
import InventoryBalanceChart from "../charts/InventoryBalanceChart";

const fmt = (n: number | null | undefined) => (n == null ? "—" : n.toLocaleString("vi-VN"));

/** Cán cân Tồn kho VRG (thay cho cán cân cung–cầu mẫu) — dữ liệu thật từ báo cáo tuần. */
export default function InventoryBalanceSection() {
  const [weeks, setWeeks] = useState<InventoryWeek[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchInventory().then(setWeeks).catch((e) => setErr(e.message));
  }, []);

  const last = weeks.filter((w) => w.ton_kho != null).at(-1);
  const free = last && last.ton_kho != null && last.ton_kho_hd != null
    ? last.ton_kho - last.ton_kho_hd : null;

  return (
    <div className="card" id="sec-tonkho">
      <div className="card-head">
        <div>
          <h3>Cán cân Tồn kho VRG · Tồn kho vs Đã có hợp đồng</h3>
          <div className="sub">Tồn kho cuối kỳ · đã có hợp đồng · tồn tự do (chưa bán) — tấn, theo tuần</div>
        </div>
        <span className="chip">Dữ liệu thật</span>
      </div>
      {err ? (
        <div className="scan-empty">Chưa tải được tồn kho: {err}</div>
      ) : weeks.length === 0 ? (
        <div className="scan-empty">Chưa có dữ liệu tồn kho.</div>
      ) : (
        <div className="chart-wrap"><InventoryBalanceChart weeks={weeks} /></div>
      )}
      <p style={{ color: "var(--muted)", fontSize: 11, margin: "10px 0 0" }}>
        Tồn tự do (tồn kho − đã có hợp đồng) cao ⇒ áp lực bán ⇒ có thể điều chỉnh giá sàn hợp lý hơn để dễ tiêu thụ.
        {last ? ` Tuần gần nhất ${last.as_of}: tồn ${fmt(last.ton_kho)} tấn · tự do ${fmt(free)} tấn.` : ""}
      </p>
    </div>
  );
}
