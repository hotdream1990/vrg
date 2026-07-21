import { useState } from "react";

import {
  type ReutersParseResult,
  parseReutersPhysical,
  upsertRecord,
} from "../../../../lib/api-client";
import { dmy } from "../../../../lib/date";
import DateInput from "../../sections/DateInput";

const STATUS_LABEL: Record<string, string> = {
  na: "NA — bỏ qua",
  unmatched: "Không khớp chủng loại",
  no_unit: "Thiếu đơn vị (baht/kg hoặc $/kg)",
  no_fx: "Thiếu tỷ giá USD/THB ngày này",
};
const canImport = (status: string) => status === "ok" || status === "derived";
const PLACEHOLDER = `Grade: Thai RSS3 (August) - 97.39 baht/kg
Grade: Thai STR20 (August) - 78.88 baht/kg
Grade: Thai 60-percent latex (bulk/August) - 57.90 baht/kg
Grade: Malaysia SMR20 (August) - $2.21/kg
Grade: Indonesia SIR20 - NA`;

/** Nhập nhanh giá physical: paste text Reuters (MarketScreener) → phân giải + quy đổi USD/tấn → thêm. */
export default function ReutersPasteImport({ defaultDate, onImported }: {
  defaultDate: string; onImported: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [date, setDate] = useState(defaultDate);
  const [res, setRes] = useState<ReutersParseResult | null>(null);
  const [sel, setSel] = useState<Record<number, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const doParse = async (d?: string) => {
    if (!text.trim()) return;
    setErr(""); setMsg(""); setBusy(true);
    try {
      const r = await parseReutersPhysical(text, d ?? (date || undefined));
      setRes(r); setDate(r.as_of);
      const s: Record<number, boolean> = {};
      r.rows.forEach((row, i) => { s[i] = canImport(row.status); });
      setSel(s);
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi phân giải"); }
    finally { setBusy(false); }
  };
  const onDate = (v: string) => { const nv = v || date; setDate(nv); if (res && text.trim()) doParse(nv); };

  const importable = (r: ReutersParseResult["rows"][number], i: number) =>
    sel[i] && canImport(r.status) && r.usd_tonne != null;
  const okCount = res ? res.rows.filter(importable).length : 0;
  const noFxCount = res ? res.rows.filter((r) => r.status === "no_fx").length : 0;

  const doImport = async () => {
    if (!res) return;
    const rows = res.rows.filter(importable);
    if (!rows.length) return;
    setBusy(true); setErr("");
    try {
      for (const r of rows) {
        await upsertRecord({ as_of: date, source: "reuters", grade: r.grade!, contract: r.contract,
          price_type: "physical", price: r.usd_tonne!, currency: "USD", unit: "USD/tonne" });
      }
      setMsg(`Đã thêm ${rows.length} dòng vào ngày ${dmy(date)}.`);
      setRes(null); setText(""); onImported();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi thêm dòng"); }
    finally { setBusy(false); }
  };

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div className="card-head" style={{ cursor: "pointer" }} onClick={() => setOpen((o) => !o)}>
        <h3>{open ? "▾" : "▸"} Nhập nhanh từ text Reuters (MarketScreener)</h3>
      </div>
      {open && (
        <div style={{ padding: "4px 4px 8px" }}>
          <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 8px" }}>
            Copy các dòng giá bên MarketScreener (không cần dòng ngày) rồi dán vào đây, <b>chọn ngày</b> ở ô bên
            dưới. Nhận cả dạng <code>Grade: Thai RSS3 (August) - 97.39 baht/kg</code> lẫn dạng bảng 2 cột
            <code> SMR20 $2.24/kg</code>. Hệ thống tự tách chủng loại + quy đổi <b>USD/tấn</b> (baht/kg ÷ USD/THB,
            $/kg ×1000), tự <b>nội suy Latex Drums = Bulk + 100</b>. Dòng thiếu tỷ giá USD/THB sẽ
            <b> không được nhập</b>.
          </p>
          <textarea className="blt-date-input" style={{ width: "100%", minHeight: 120, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
            value={text} placeholder={PLACEHOLDER} onChange={(e) => setText(e.target.value)} />
          <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "8px 0" }}>
            <label className="blt-date-label" style={{ margin: 0 }}>Ngày:
              <DateInput value={date} noFuture onChange={onDate} />
            </label>
            <button className="btn btn-primary" onClick={() => doParse()} disabled={busy || !text.trim()}>
              {busy ? <span className="spinner" /> : null} Phân giải
            </button>
          </div>

          {res && (
            <div style={{ fontSize: 12, margin: "2px 0 8px", color: res.usd_thb != null ? "var(--muted)" : "#d08a1a" }}>
              {res.usd_thb != null ? (
                <>Tỷ giá quy đổi baht/kg (đúng ngày {dmy(res.as_of)}):{" "}
                  <b>USD/THB = {res.usd_thb.toLocaleString("vi-VN", { maximumFractionDigits: 4 })}</b></>
              ) : (
                <>Chưa có tỷ giá USD/THB <b>đúng ngày {dmy(date)}</b> — các dòng baht/kg không quy đổi được và
                  sẽ không được nhập (không lấy tỷ giá ngày khác). Hãy cập nhật tỷ giá ngày này ở trang Tỷ giá.</>
              )}
            </div>
          )}

          {err && <div className="blt-error">{err}</div>}
          {msg && <div className="blt-info">{msg}</div>}

          {res?.note && (
            <div style={{ background: res.note_as_of && res.note_as_of !== date ? "#4a1f1f" : "#4a3410",
              border: `1px solid ${res.note_as_of && res.note_as_of !== date ? "#c0504d" : "#d08a1a"}`,
              color: res.note_as_of && res.note_as_of !== date ? "#f0a0a0" : "#f0c26a",
              borderRadius: 6, padding: "8px 12px", margin: "8px 0", fontSize: 13 }}>
              ⚠ Reuters ghi chú: <b>“{res.note}”</b>.{" "}
              {res.note_as_of && res.note_as_of !== date ? (
                <>Giá này là của <b>ngày {dmy(res.note_as_of)}</b>, không phải ngày bạn chọn
                  ({dmy(date)}). Đổi ô <b>Ngày</b> về {dmy(res.note_as_of)} rồi phân giải lại — không nhập
                  giá của ngày này sang ngày khác.</>
              ) : (
                <>Kiểm tra ngày đang chọn ({dmy(date)}) có đúng ngày của giá không.</>
              )}
            </div>
          )}

          {res && noFxCount > 0 && (
            <div style={{ background: "#4a3410", border: "1px solid #d08a1a", color: "#f0c26a",
              borderRadius: 6, padding: "8px 12px", margin: "8px 0", fontSize: 13 }}>
              ⚠ {noFxCount} dòng (baht/kg) <b>chưa quy đổi được</b> vì thiếu tỷ giá USD/THB ngày {dmy(date)}.
              Cập nhật tỷ giá ở trang <b>Tỷ giá</b> rồi bấm <b>Phân giải</b> lại — các dòng này sẽ không được thêm.
            </div>
          )}

          {res && (
            <>
              <table className="wk-table" style={{ fontSize: 12, marginTop: 6 }}>
                <thead>
                  <tr>
                    <th style={{ width: 34 }} />
                    <th>Chủng loại</th><th className="r">Giá gốc</th><th className="r">→ USD/tấn</th><th>Ghi chú</th>
                  </tr>
                </thead>
                <tbody>
                  {res.rows.map((r, i) => (
                    <tr key={i} style={{ opacity: canImport(r.status) ? 1 : 0.55 }}>
                      <td className="c">
                        <input type="checkbox" checked={!!sel[i]} disabled={!canImport(r.status)}
                          onChange={(e) => setSel((s) => ({ ...s, [i]: e.target.checked }))} />
                      </td>
                      <td>{r.grade ?? <span style={{ color: "var(--muted)" }}>{r.label}</span>}</td>
                      <td className="r">{r.native_price != null ? `${r.native_price} ${r.native_unit ?? ""}` : "—"}</td>
                      <td className="r">{r.usd_tonne != null ? r.usd_tonne.toLocaleString("en-US") : "—"}</td>
                      <td style={{ color: r.status === "derived" ? "#3a9d78" : r.status === "ok" ? "var(--muted)" : "#d08a1a" }}>
                        {r.status === "derived" ? `Nội suy = Bulk + ${100}`
                          : r.status === "ok" ? (r.contract ? `HĐ ${r.contract}` : "")
                          : STATUS_LABEL[r.status] ?? r.status}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <button className="btn btn-primary" style={{ marginTop: 8 }} onClick={doImport} disabled={busy || okCount === 0}>
                {busy ? <span className="spinner" /> : null} Thêm {okCount} dòng vào ngày {dmy(date)}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
