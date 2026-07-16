import { ExperimentOutlined, ReloadOutlined } from "@ant-design/icons";
import { Segmented } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { buildGridPrevMap } from "../../../lib/change-warning";
import { dmy } from "../../../lib/date";
import {
  type MemberPriceType,
  type MemberPrices,
  type UnitSheet,
  clearMyPrice,
  fetchMyPrices,
  upsertMyPrice,
} from "../../../lib/member-client";
import EditableCell from "../sections/EditableCell";
import "../../bulletin/bulletin.css";

const COLS: { key: MemberPriceType; label: string; unit: string }[] = [
  { key: "purchase", label: "Giá mủ nước", unit: "đồng/độ TSC" },
  { key: "purchase_cup", label: "Giá mủ chén", unit: "đồng/kg" },
];
const EMPTY_SHEET: UnitSheet = { purchase: {}, purchase_cup: {}, dates: [] };

/** Lùi `delta` ngày từ 1 ISO date (YYYY-MM-DD), trả ISO date. */
function shiftISO(iso: string, delta: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() + delta);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())}`;
}

/** Tài khoản đơn vị thành viên: tự xem/nhập giá mủ nước + mủ chén của CÁC đơn vị được gán. */
export default function MemberPricePage() {
  const [data, setData] = useState<MemberPrices | null>(null);
  const [unit, setUnit] = useState<string>(""); // đơn vị đang xem/nhập
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setErr("");
    fetchMyPrices(60)
      .then((d) => {
        setData(d);
        setUnit((u) => (u && d.units.includes(u) ? u : d.units[0] ?? ""));
      })
      .catch((e) => setErr(e.message));
  }, []);
  useEffect(() => { load(); }, [load]);

  const today = data?.today ?? "";
  const win = data?.edit_window_days ?? 7;
  const units = data?.units ?? [];
  const sheet = (unit && data?.sheets[unit]) || EMPTY_SHEET;

  // Ngày sửa được: hôm nay lùi `win` ngày — luôn hiển thị để nhập kể cả chưa có số.
  const editableDates = useMemo(
    () => (today ? Array.from({ length: win + 1 }, (_, i) => shiftISO(today, -i)) : []),
    [today, win],
  );
  const editable = useMemo(() => new Set(editableDates), [editableDates]);

  const values = useMemo(
    () => ({ purchase: sheet.purchase, purchase_cup: sheet.purchase_cup }),
    [sheet],
  );

  // Hàng = ngày sửa được + ngày có dữ liệu (mới nhất trước).
  const rows = useMemo(
    () => [...new Set([...editableDates, ...sheet.dates])].sort().reverse(),
    [editableDates, sheet],
  );

  // prev[series][date] = giá gần nhất trước đó → cảnh báo lệch ≥10% khi nhập tay.
  const prevOf = useMemo(() => buildGridPrevMap(["purchase", "purchase_cup"], rows, values), [rows, values]);

  const save = (col: MemberPriceType, d: string, price: number) =>
    upsertMyPrice(unit, d, col, price).then(load).catch((e) => setErr(e.message));
  const clear = (col: MemberPriceType, d: string) =>
    clearMyPrice(unit, d, col).then(load).catch((e) => setErr(e.message));

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ExperimentOutlined style={{ marginRight: 8 }} />Giá thu mua</h2>
          <p>
            Tự nhập giá thu mua mủ nước (đồng/độ TSC) và mủ chén (đồng/kg) của các đơn vị được gán.
            Chỉ nhập/sửa được hôm nay và {win} ngày gần nhất; ngày cũ hơn chỉ để xem.
          </p>
        </div>
        <div className="actions">
          <button className="btn" onClick={load}><ReloadOutlined style={{ marginRight: 6 }} />Tải lại</button>
        </div>
      </div>

      {units.length > 1 ? (
        <div style={{ marginBottom: 12, overflowX: "auto" }}>
          <Segmented value={unit} onChange={(v) => setUnit(v as string)} options={units} />
        </div>
      ) : units.length === 1 ? (
        <p style={{ margin: "0 0 12px", color: "var(--muted)" }}>Đơn vị: <b>{units[0]}</b></p>
      ) : null}

      {err && <div className="blt-error">{err}</div>}

      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table style={{ fontSize: 13 }}>
          <thead>
            <tr>
              <th>Ngày</th>
              {COLS.map((c) => (
                <th key={c.key} className="r" style={{ whiteSpace: "nowrap" }}>
                  {c.label}
                  <br />
                  <span style={{ fontWeight: 400, color: "var(--muted)", fontSize: 11 }}>{c.unit}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => {
              const ed = editable.has(d);
              return (
                <tr key={d}>
                  <td style={{ whiteSpace: "nowrap", fontWeight: 500 }}>
                    {dmy(d)}
                    {!ed && (
                      <span style={{ marginLeft: 6, color: "var(--muted)", fontSize: 11 }}>(chỉ xem)</span>
                    )}
                  </td>
                  {COLS.map((c) => (
                    <td key={c.key} className="r">
                      <EditableCell
                        value={values[c.key][d] ?? null} prevValue={prevOf[c.key]?.[d]}
                        onSave={(n) => save(c.key, d, n)} onClear={() => clear(c.key, d)} readOnly={!ed || !unit} />
                    </td>
                  ))}
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={COLS.length + 1} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                  Chưa có dữ liệu.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
