import { Fragment, useCallback, useEffect, useRef, useState } from "react";

import {
  type PriceSheet,
  type SheetCol,
  fetchSheet,
  upsertRecord,
} from "../../../lib/api-client";
import { dmy } from "../../../lib/date";

const fmt = (v: number | null | undefined, d = 0) =>
  v == null ? "" : v.toLocaleString("vi-VN", { maximumFractionDigits: d });

const colSpan = (c: SheetCol) => (c.show_native ? 1 : 0) + (c.show_fx ? 1 : 0) + 1;
const LINE = "1px solid var(--line, #1e293b)";
const GRP = "2px solid var(--line, #334155)";

// fact_price key cho ô tỷ giá (USD/JPY → currency JPY, unit "JPY per USD").
const fxRecord = (pair: string, price: number) => {
  const cur = pair.split("/")[1];
  return { source: "fx", grade: pair, contract: "", price_type: "fx",
    price, currency: cur, unit: `${cur} per USD` };
};

type Rec = Parameters<typeof upsertRecord>[0];

/** Lưới giá giống sheet mẫu VRG. view="exchange" = giá sàn (Native·Tỷ giá·USD); "fx" = tỷ giá.
    Đọc DB (lọc khoảng ngày), USD tự tính (backend). Sửa ô → ghi đè fact_price. */
export default function PriceSheetGrid({
  view = "exchange",
  dateFrom,
  dateTo,
  onSaved,
  readOnly = false,
}: { view?: "exchange" | "fx"; dateFrom?: string; dateTo?: string; onSaved?: () => void; readOnly?: boolean }) {
  const [sheet, setSheet] = useState<PriceSheet | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [val, setVal] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const cancelRef = useRef(false); // Esc đặt cờ này để onBlur không lưu

  const load = useCallback(() => {
    fetchSheet({ dateFrom, dateTo, days: 30 }).then(setSheet).catch((e) => setErr(e.message));
  }, [dateFrom, dateTo]);
  useEffect(() => { load(); }, [load]);

  if (err && !sheet) return <div className="blt-error">Lỗi tải lưới: {err}</div>;
  if (!sheet) return null;

  const cols = sheet.groups.flatMap((g) => g.cols);

  const commit = async (rec: Rec) => {
    setBusy(true); setErr("");
    try { await upsertRecord(rec); load(); onSaved?.(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi lưu"); }
    finally { setBusy(false); setEditing(null); }
  };

  // Ô sửa được: input khi đang sửa, ngược lại span bấm-để-sửa. raw = số gốc để prefill.
  // readOnly (viewer): chỉ hiển thị số, không cho sửa.
  const cell = (id: string, raw: number | null | undefined, dec: number, save: (n: number) => void) =>
    readOnly ? (
      raw != null ? <>{fmt(raw, dec)}</> : <span style={{ color: "var(--muted)" }}>—</span>
    ) : editing === id ? (
      <input
        className="blt-cell-input" autoFocus disabled={busy} value={val}
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();                 // → lưu qua onBlur
          else if (e.key === "Escape") { cancelRef.current = true; e.currentTarget.blur(); }
        }}
        onBlur={() => {
          if (cancelRef.current) { cancelRef.current = false; setEditing(null); return; }
          const n = Number(val.replace(/[,\s]/g, ""));
          if (val.trim() && !isNaN(n)) save(n); else setEditing(null);
        }}
        style={{ width: 60, padding: "2px 4px", fontSize: 11 }}
      />
    ) : (
      <span onClick={() => { setEditing(id); setVal(raw != null ? String(raw) : ""); }}
        style={{ cursor: "pointer", display: "block", minWidth: 44 }}>
        {raw != null ? fmt(raw, dec) : <span style={{ color: "var(--muted)" }}>—</span>}
      </span>
    );

  const empty = sheet.rows.length === 0;

  return (
    <div className="card" style={{ padding: 0, overflow: "auto" }}>
      {err && <div className="blt-error" style={{ margin: "8px 16px" }}>{err}</div>}

      {view === "exchange" && (
        <table style={{ fontSize: 11 }}>
          <thead>
            <tr>
              <th rowSpan={3}>Ngày</th>
              {sheet.groups.map((g) => (
                <th key={g.exchange} colSpan={g.cols.reduce((s, c) => s + colSpan(c), 0)}
                  style={{ textAlign: "center", borderLeft: GRP }}>{g.label}</th>
              ))}
            </tr>
            <tr>
              {cols.map((c) => (
                <th key={c.key} colSpan={colSpan(c)} style={{ textAlign: "center", borderLeft: GRP }}>{c.label}</th>
              ))}
            </tr>
            <tr>
              {cols.map((c) => (
                <Fragment key={c.key}>
                  {c.show_native && <th className="r" style={{ borderLeft: GRP }}>{c.native_label}</th>}
                  {c.show_fx && <th className="r">Tỷ giá</th>}
                  <th className="r" style={{ borderLeft: c.show_native || c.show_fx ? LINE : GRP }}>USD/T</th>
                </Fragment>
              ))}
            </tr>
          </thead>
          <tbody>
            {sheet.rows.map((row) => (
              <tr key={row.as_of}>
                <td style={{ whiteSpace: "nowrap", fontWeight: 500 }}>{dmy(row.as_of)}</td>
                {cols.map((c) => {
                  const cv = row.cells[c.key] ?? {};
                  const e = c.edit;
                  return (
                    <Fragment key={c.key}>
                      {c.show_native && (
                        <td className="r" style={{ borderLeft: GRP }}>
                          {cell(`${row.as_of}|${c.key}|n`, cv.native, 3,
                            (n) => commit({ as_of: row.as_of, source: e.source, grade: e.grade, contract: "", price_type: e.price_type, price: n, currency: e.currency, unit: e.unit }))}
                        </td>
                      )}
                      {c.show_fx && c.fx_pair && (
                        <td className="r">
                          {cell(`${row.as_of}|${c.key}|fx`, cv.fx_rate, 4,
                            (n) => commit({ as_of: row.as_of, ...fxRecord(c.fx_pair!, n) }))}
                        </td>
                      )}
                      <td className="r" style={{ fontWeight: 600, borderLeft: c.show_native || c.show_fx ? LINE : GRP }}>
                        {cell(`${row.as_of}|${c.key}|u`, cv.usd, 0,
                          (n) => commit({ as_of: row.as_of, source: e.source, grade: e.grade, contract: "", price_type: e.price_type, price: n * e.scale, currency: e.currency, unit: e.unit }))}
                      </td>
                    </Fragment>
                  );
                })}
              </tr>
            ))}
            {empty && (
              <tr><td colSpan={99} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                Chưa có dữ liệu giá sàn trong khoảng ngày — bấm “Quét giá ngay” hoặc đổi khoảng ngày.
              </td></tr>
            )}
          </tbody>
        </table>
      )}

      {view === "fx" && (
        <table style={{ fontSize: 11 }}>
          <thead>
            <tr><th>Ngày</th>{sheet.fx_pairs.map((p) => <th key={p} className="r">{p}</th>)}</tr>
          </thead>
          <tbody>
            {sheet.rows.map((row) => (
              <tr key={row.as_of}>
                <td style={{ whiteSpace: "nowrap", fontWeight: 500 }}>{dmy(row.as_of)}</td>
                {sheet.fx_pairs.map((p) => (
                  <td key={p} className="r">
                    {cell(`${row.as_of}|fxblk|${p}`, row.fx[p], 4,
                      (n) => commit({ as_of: row.as_of, ...fxRecord(p, n) }))}
                  </td>
                ))}
              </tr>
            ))}
            {empty && (
              <tr><td colSpan={99} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                Chưa có tỷ giá trong khoảng ngày — bấm “Quét giá ngay” hoặc đổi khoảng ngày.
              </td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
