import { Fragment, useEffect, useState } from "react";

import { type PriceBoard, type PriceSheet, fetchBoard, fetchSheet } from "../../../lib/api-client";
import { getFloor, listFloors } from "../../../lib/floor-client";

type Cmp = { product: string; vrg: number; market: number; marketLabel: string; diffPct: number };

// Map chủng loại giá sàn VRG → grade thị trường (board dùng mã sàn "MRE").
const FLOOR_MAP: Record<string, "RSS3" | "SMR20" | "LATEX" | "SMRCV"> = {
  "RSS 3": "RSS3", "SVR 20": "SMR20", "LATEX": "LATEX", "SVR CV 50": "SMRCV", "SVR CV60": "SMRCV",
};
// Heatmap % thay đổi: hàng = grade, cột = sàn (sheet dùng mã "MRB").
const HM_COLS = ["OSE", "SHANGHAI", "SGX", "MRB"];
const HM_ROWS = ["RSS3", "TSR20", "SMRCV", "SMR20", "LATEX"];

const vnum = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
const note = (d: number) => (d <= -2 ? "Sàn thấp hơn TT" : d >= 2 ? "Sàn cao hơn TT" : "Sát thị trường");

function marketUsd(board: PriceBoard, mkt: string): { usd: number; label: string } | null {
  const find = (ex: string, gr: string) =>
    board.exchanges.find((e) => e.exchange === ex && e.grade === gr)?.usd_tonne ?? null;
  let usd: number | null = null, label = "";
  if (mkt === "RSS3") { usd = find("OSE", "RSS3"); label = "OSE"; if (usd == null) { usd = find("SHANGHAI", "RSS3"); label = "SHANGHAI"; } }
  else if (mkt === "SMR20") { usd = find("MRE", "SMR20"); label = "MRE"; if (usd == null) { usd = find("OSE", "TSR20"); label = "OSE·TSR20"; } }
  else if (mkt === "LATEX") { usd = find("MRE", "LATEX"); label = "MRE"; }
  else if (mkt === "SMRCV") { usd = find("MRE", "SMRCV"); label = "MRE"; }
  return usd != null ? { usd, label } : null;
}

// % thay đổi phiên gần nhất của (sàn, grade) từ bảng tính giá (USD/T đã quy đổi).
function pctChange(sheet: PriceSheet, exchange: string, grade: string): number | null {
  const col = sheet.groups.find((g) => g.exchange.toUpperCase() === exchange.toUpperCase())
    ?.cols.find((c) => c.grade.toUpperCase() === grade.toUpperCase());
  if (!col) return null;
  const s = [...sheet.rows].sort((a, b) => a.as_of.localeCompare(b.as_of))
    .map((r) => r.cells[col.key]?.usd).filter((v): v is number => v != null);
  if (s.length < 2 || !s[s.length - 2]) return null;
  return ((s[s.length - 1] - s[s.length - 2]) / s[s.length - 2]) * 100;
}

const hmStyle = (p: number | null) =>
  p == null ? { color: "var(--muted)" }
    : { background: p > 0 ? "#16a34a22" : p < 0 ? "#ef444422" : "transparent", color: p > 0 ? "#0b7a3b" : p < 0 ? "#c0392b" : "var(--muted)", fontWeight: 600 };

/** Heatmap %thay đổi + So sánh Giá sàn Tập đoàn vs Thị trường — DỮ LIỆU THẬT (sheet + floor↔board). */
export default function HeatmapAndVrg() {
  const [rows, setRows] = useState<Cmp[] | null>(null);
  const [meta, setMeta] = useState<{ lan: number; as_of: string } | null>(null);
  const [hm, setHm] = useState<Record<string, Record<string, number | null>> | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const sheet = await fetchSheet({ days: 30 });
        const m: Record<string, Record<string, number | null>> = {};
        HM_ROWS.forEach((g) => { m[g] = {}; HM_COLS.forEach((ex) => { m[g][ex] = pctChange(sheet, ex, g); }); });
        setHm(m);
      } catch { setHm({}); }
      try {
        const list = await listFloors();
        if (!list.length) { setRows([]); return; }
        const [sch, board] = await Promise.all([getFloor(list[0].lan), fetchBoard()]);
        setMeta({ lan: sch.lan, as_of: sch.as_of });
        const out: Cmp[] = [];
        for (const it of sch.items) {
          const mkt = FLOOR_MAP[it.grade];
          if (!mkt || it.fob_usd == null) continue;
          const mk = marketUsd(board, mkt);
          if (!mk) continue;
          out.push({ product: it.grade, vrg: it.fob_usd, market: mk.usd, marketLabel: mk.label, diffPct: ((it.fob_usd - mk.usd) / mk.usd) * 100 });
        }
        setRows(out);
      } catch { setRows([]); }
    })();
  }, []);

  const hmReady = hm != null && HM_ROWS.some((g) => HM_COLS.some((ex) => hm[g]?.[ex] != null));
  const cmpReady = rows != null && rows.length > 0;

  return (
    <div className="grid-2" id="sec-giasan">
      <div className="card">
        <div className="card-head">
          <h3 className={hmReady ? undefined : "title-demo"}>Heatmap · % Thay đổi theo sàn × sản phẩm</h3>
          <span className={`chip ${hmReady ? "" : "demo"}`}>{hmReady ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
        </div>
        <div className="heatmap" style={{ gridTemplateColumns: `90px repeat(${HM_COLS.length}, 1fr)` }}>
          <div className="hm-head" />
          {HM_COLS.map((c) => <div className="hm-head" key={c}>{c}</div>)}
          {HM_ROWS.map((g) => (
            <Fragment key={g}>
              <div className="hm-label">{g}</div>
              {HM_COLS.map((ex) => {
                const p = hm?.[g]?.[ex] ?? null;
                return <div className="hm-cell" key={ex} style={hmStyle(p)}>{p == null ? "—" : `${p >= 0 ? "+" : ""}${p.toFixed(2)}%`}</div>;
              })}
            </Fragment>
          ))}
        </div>
        <p style={{ color: "var(--muted)", fontSize: 11, margin: "12px 0 0" }}>
          % thay đổi phiên gần nhất (USD/T quy đổi). Ô "—" = sàn đó chưa có nguồn cho chủng loại.
        </p>
      </div>

      <div className="card">
        <div className="card-head">
          <div>
            <h3 className={cmpReady ? undefined : "title-demo"}>So sánh Giá sàn Tập đoàn vs Thị trường</h3>
            {meta && <div className="sub">Giá sàn lần {meta.lan} ({meta.as_of}) · FOB USD/T ↔ giá giao ngay quy đổi</div>}
          </div>
          <span className={`chip ${cmpReady ? "" : "demo"}`}>{cmpReady ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
        </div>
        {rows == null ? (
          <div className="scan-empty">Đang tải…</div>
        ) : rows.length === 0 ? (
          <div className="scan-empty">Chưa có giá sàn hoặc giá thị trường để so sánh.</div>
        ) : (
          <table>
            <thead>
              <tr><th>Sản phẩm</th><th className="r">Giá sàn VRG</th><th className="r">Giá TT giao ngay</th><th className="r">Chênh lệch</th><th>Nhận định</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.product}>
                  <td style={{ fontWeight: 500 }}>{r.product}</td>
                  <td className="r">{vnum(r.vrg)}</td>
                  <td className="r">{vnum(r.market)} <span style={{ color: "var(--muted)", fontSize: 11 }}>({r.marketLabel})</span></td>
                  <td className="r" style={{ fontWeight: 600, color: r.diffPct > 0 ? "#c0392b" : r.diffPct < 0 ? "#0b7a3b" : "#5f6f67" }}>
                    {r.diffPct >= 0 ? "+" : ""}{r.diffPct.toFixed(1)}%
                  </td>
                  <td><span className={`chip ${Math.abs(r.diffPct) >= 2 ? "warn" : ""}`}>{note(r.diffPct)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
