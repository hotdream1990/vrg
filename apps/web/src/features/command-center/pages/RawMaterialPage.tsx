import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  type PurchaseSheet,
  deletePurchaseDate,
  fetchPurchaseSheet,
  upsertRecord,
} from "../../../lib/api-client";
import DateRangeBar from "../sections/DateRangeBar";
import EditableCell from "../sections/EditableCell";
import "../../bulletin/bulletin.css";

const todayISO = () => new Date().toISOString().slice(0, 10);
const STICKY = { position: "sticky" as const, left: 0, background: "var(--card, #0d1117)", zIndex: 1 };

/** Quản lý số liệu → Giá mủ nguyên liệu: lưới hàng=ngày × cột=đơn vị (đồng/độ TSC). */
export default function RawMaterialPage() {
  const [sheet, setSheet] = useState<PurchaseSheet | null>(null);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [newDate, setNewDate] = useState(todayISO());
  const [extraDates, setExtraDates] = useState<string[]>([]);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setErr("");
    fetchPurchaseSheet(from || undefined, to || undefined).then(setSheet).catch((e) => setErr(e.message));
  }, [from, to]);
  useEffect(() => { load(); }, [load]);

  // Hàng = ngày có data + ngày vừa "Thêm" (mới nhất trước).
  const dates = useMemo(() => {
    const set = new Set([...extraDates, ...(sheet?.dates ?? [])]);
    return [...set].sort().reverse();
  }, [sheet, extraDates]);
  const companies = sheet?.companies ?? [];

  const saveCell = (company: string, date: string, price: number) =>
    upsertRecord({ as_of: date, source: "vrg", grade: company, contract: "",
      price_type: "purchase", price, currency: "VND", unit: "đồng/độ TSC" })
      .then(load).catch((e) => setErr(e.message));

  const addDate = () => {
    if (newDate && !dates.includes(newDate)) setExtraDates((d) => [...new Set([...d, newDate])]);
  };
  const delDate = (d: string) => {
    if (!confirm(`Xoá toàn bộ giá thu mua ngày ${d}?`)) return;
    deletePurchaseDate(d)
      .then(() => { setExtraDates((x) => x.filter((e) => e !== d)); load(); })
      .catch((e) => setErr(e.message));
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2>🪣 Giá mủ nguyên liệu</h2>
          <p>Giá thu mua mủ nước theo đơn vị thành viên VRG (đồng/độ TSC) — hàng là ngày, cột là đơn vị. Bấm ô để sửa.</p>
        </div>
        <div className="actions">
          <Link className="btn" to="/quan-ly-so-lieu/don-vi-thanh-vien">🏢 Quản lý đơn vị</Link>
        </div>
      </div>

      <DateRangeBar from={from} to={to} onFrom={setFrom} onTo={setTo} onReload={load}
        info={`${dates.length} ngày · ${companies.length} đơn vị`}>
        <label className="blt-date-label">Thêm ngày:
          <input type="date" className="blt-date-input" value={newDate}
            onChange={(e) => setNewDate(e.target.value)} />
        </label>
        <button className="btn btn-primary" onClick={addDate}>＋ Thêm ngày</button>
      </DateRangeBar>

      {err && <div className="blt-error">{err}</div>}

      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table style={{ fontSize: 12 }}>
          <thead>
            <tr>
              <th style={STICKY}>Ngày</th>
              {companies.map((co) => (
                <th key={co} className="r" style={{ whiteSpace: "nowrap" }}>{co}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dates.map((d) => (
              <tr key={d}>
                <td style={{ ...STICKY, whiteSpace: "nowrap", fontWeight: 500 }}>
                  {d}{" "}
                  <button className="blt-rm-btn" title="Xoá ngày" onClick={() => delDate(d)}
                    style={{ fontSize: 11 }}>✕</button>
                </td>
                {companies.map((co) => (
                  <td key={co} className="r">
                    <EditableCell value={sheet?.values[co]?.[d] ?? null} onSave={(n) => saveCell(co, d, n)} />
                  </td>
                ))}
              </tr>
            ))}
            {dates.length === 0 && (
              <tr><td colSpan={companies.length + 1} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                Chưa có ngày nào — chọn ngày rồi bấm "＋ Thêm ngày" để nhập.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
