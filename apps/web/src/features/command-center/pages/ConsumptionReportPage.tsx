import { ExportOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  type ConsumptionSummary,
  type ContractMeta,
  type UndeliveredSummary,
  fetchConsumption,
  fetchContractMeta,
  fetchUndelivered,
} from "../../../lib/sales-contract-client";
import DateInput from "../sections/DateInput";
import "../../bulletin/bulletin.css";

const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });
const ty = (n: number | null) =>
  (n == null ? "—" : (n / 1_000_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));

const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => `${new Date().toISOString().slice(0, 7)}-01`;

/** Báo cáo → Tiêu thụ: số TÍNH TỪ HỢP ĐỒNG (các lần giao), KHÔNG còn biểu nhập tay. */
export default function ConsumptionReportPage() {
  const [meta, setMeta] = useState<ContractMeta | null>(null);
  const [from, setFrom] = useState(monthStart());
  const [to, setTo] = useState(today());
  const [rows, setRows] = useState<Record<string, ConsumptionSummary>>({});
  const [undelivered, setUndelivered] = useState<Record<string, UndeliveredSummary>>({});
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    if (!from || !to) return;
    setLoading(true); setErr("");
    Promise.all([fetchConsumption(from, to), fetchUndelivered(to)])
      .then(([c, u]) => { setRows(c.by_company); setUndelivered(u.by_company); })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [from, to]);

  useEffect(() => { fetchContractMeta().then(setMeta).catch((e) => setErr(e.message)); }, []);
  useEffect(() => { load(); }, [load]);

  const companies = useMemo(
    () => Array.from(new Set([...Object.keys(rows), ...Object.keys(undelivered)])).sort(),
    [rows, undelivered]);

  const totals = useMemo(() => {
    const acc = { qty: 0, qty_dry: 0, cost: 0, revenue: 0 as number | null, deliveries: 0, remaining: 0 };
    for (const c of companies) {
      const r = rows[c];
      if (r) {
        acc.qty += r.qty; acc.qty_dry += r.qty_dry; acc.cost += r.cost; acc.deliveries += r.deliveries;
        if (r.revenue == null) acc.revenue = null;
        else if (acc.revenue != null) acc.revenue += r.revenue;
      }
      acc.remaining += undelivered[c]?.qty ?? 0;
    }
    return acc;
  }, [companies, rows, undelivered]);

  const ch = (c: string, k: string) => rows[c]?.by_channel?.[k] ?? 0;

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ExportOutlined style={{ marginRight: 8 }} />Báo cáo tiêu thụ</h2>
          <p>
            Tổng hợp từ <b>các lần giao</b> ghi trên hợp đồng &amp; phụ lục — đơn vị không nhập tay
            số tiêu thụ nữa. Cột <b>Chưa giao</b> lấy tại ngày cuối kỳ.
          </p>
        </div>
      </div>

      <div className="blt-toolbar">
        <label className="blt-date-label">Từ ngày<DateInput value={from} onChange={setFrom} /></label>
        <label className="blt-date-label">Đến ngày<DateInput value={to} onChange={setTo} /></label>
        <button className="btn" onClick={load} disabled={loading}>{loading ? "Đang tải…" : "Tải lại"}</button>
        <span style={{ color: "var(--muted)", fontSize: 13 }}>{companies.length} đơn vị</span>
      </div>

      {err && <div className="blt-error">{err}</div>}

      <div className="kpi-row">
        <div className="kpi"><div className="label">Sản lượng tiêu thụ (tấn)</div><div className="value">{t3(totals.qty)}</div></div>
        <div className="kpi"><div className="label">Quy khô (tấn)</div><div className="value">{t3(totals.qty_dry)}</div></div>
        <div className="kpi"><div className="label">Doanh thu (tỷ đồng)</div><div className="value">{ty(totals.revenue)}</div></div>
        <div className="kpi"><div className="label">Chi phí dòng bán (tr.đ)</div><div className="value">{t3(totals.cost)}</div></div>
        <div className="kpi"><div className="label">Số lần giao</div><div className="value">{totals.deliveries}</div></div>
        <div className="kpi"><div className="label">Đã ký chưa giao (tấn)</div><div className="value">{t3(totals.remaining)}</div></div>
      </div>

      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table>
          <thead><tr>
            <th>Đơn vị</th><th className="r">Lần giao</th><th className="r">SL (tấn)</th>
            <th className="r">Quy khô</th>
            <th className="r">{meta?.channels.export ?? "Xuất khẩu"}</th>
            <th className="r">{meta?.channels.domestic ?? "Trong nước"}</th>
            <th className="r">{meta?.channels.internal ?? "Nội bộ"}</th>
            <th className="r">Doanh thu (tỷ đ)</th><th className="r">Chi phí (tr.đ)</th>
            <th className="r">Chưa giao (tấn)</th>
          </tr></thead>
          <tbody>
            {companies.map((c) => (
              <tr key={c}>
                <td style={{ fontWeight: 500 }}>{c}</td>
                <td className="r">{rows[c]?.deliveries ?? 0}</td>
                <td className="r">{t3(rows[c]?.qty ?? 0)}</td>
                <td className="r">{t3(rows[c]?.qty_dry ?? 0)}</td>
                <td className="r">{t3(ch(c, "export"))}</td>
                <td className="r">{t3(ch(c, "domestic"))}</td>
                <td className="r">{t3(ch(c, "internal"))}</td>
                <td className="r">{ty(rows[c]?.revenue ?? null)}</td>
                <td className="r">{t3(rows[c]?.cost ?? 0)}</td>
                <td className="r">{t3(undelivered[c]?.qty ?? 0)}</td>
              </tr>
            ))}
            {companies.length === 0 && !loading && (
              <tr><td colSpan={10} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                Chưa có lần giao nào trong kỳ.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="form-note" style={{ fontSize: 11.5, marginTop: 10 }}>
        Doanh thu hiện “—” khi có lần giao bán bằng ngoại tệ mà chưa nhập tỷ giá — hệ thống không tự
        suy ra tỷ giá của ngày khác. Bổ sung tỷ giá trên phụ lục để có số đầy đủ.
      </div>
    </div>
  );
}
