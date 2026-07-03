import { useEffect, useState } from "react";

import { dmy } from "../../../lib/date";
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

  const last = weeks
    .filter((w) => w.ton_kho != null)
    .slice()
    .sort((a, b) => a.as_of.localeCompare(b.as_of)) // API trả DESC → tuần mới nhất = cuối
    .at(-1);
  const free = last && last.ton_kho != null && last.ton_kho_hd != null
    ? last.ton_kho - last.ton_kho_hd : null;

  return (
    <div className="card" id="sec-tonkho">
      <div className="card-head">
        <div>
          <h3>Cơ cấu Tồn kho VRG · Đã ký HĐ + Tồn tự do</h3>
          <div className="sub">Mỗi cột = tồn kho tổng = đã ký hợp đồng (đã có bên mua) + tồn tự do (chưa ký) — tấn, theo tuần</div>
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
        Đã ký HĐ là phần tồn đã có bên cam kết mua; tồn tự do = tồn tổng − đã ký. Tồn tự do cao ⇒ áp lực bán ⇒ có thể điều chỉnh giá sàn hợp lý hơn để dễ tiêu thụ.
        {last ? ` Tuần gần nhất ${dmy(last.as_of)}: tồn ${fmt(last.ton_kho)} tấn = đã ký ${fmt(last.ton_kho_hd)} + tự do ${fmt(free)} tấn.` : ""}
      </p>
    </div>
  );
}
