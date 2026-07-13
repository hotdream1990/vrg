import { useEffect, useState } from "react";

import { fetchPhysicalSheet } from "../../../../lib/api-client";
import { dm } from "../../../../lib/date";

type Row = { grade: string; cur: number; pct: number | null };
const vnum = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
const chgColor = (p: number | null) => (p == null ? "#5f6f67" : p > 0 ? "#0b7a3b" : p < 0 ? "#c0392b" : "#5f6f67");

/** Giá physical (Reuters, giao ngay) — mức mới nhất + %thay đổi so phiên trước, USD/tấn. */
export default function PhysicalBlock() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [meta, setMeta] = useState<{ cur: string; prev: string | null } | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetchPhysicalSheet().then((ph) => {
      if (!ph.dates.length) { setRows([]); return; }
      const cur = ph.dates[0], prev = ph.dates[1] ?? null;
      setMeta({ cur, prev });
      const out: Row[] = [];
      ph.grades.forEach((g) => {
        const c = ph.values[g]?.[cur];
        if (c == null) return;
        const p = prev ? ph.values[g]?.[prev] : null;
        out.push({ grade: g, cur: c, pct: p != null && p ? ((c - p) / p) * 100 : null });
      });
      setRows(out);
    }).catch((e) => setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu"));
  }, []);

  const ready = !!rows && rows.length > 0;
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3 className={ready ? undefined : "title-demo"}>Giá Physical (giao ngay)</h3>
          {meta && <div className="sub">Reuters · phiên {dm(meta.cur)}{meta.prev ? ` so ${dm(meta.prev)}` : ""} (USD/tấn)</div>}
        </div>
        <span className={`chip ${ready ? "" : "demo"}`}>{ready ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
      </div>
      {err ? <div className="scan-empty">{err}</div>
        : !rows ? <div className="scan-empty">Đang tải…</div>
        : rows.length === 0 ? <div className="scan-empty">Chưa có giá physical.</div>
        : (
          <div style={{ maxHeight: 300, overflow: "auto" }}>
            <table>
              <thead><tr><th>Chủng loại</th><th className="r">USD/tấn</th><th className="r">± phiên</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.grade}>
                    <td style={{ fontWeight: 500 }}>{r.grade}</td>
                    <td className="r">{vnum(r.cur)}</td>
                    <td className="r" style={{ fontWeight: 600, color: chgColor(r.pct) }}>
                      {r.pct == null ? "—" : `${r.pct >= 0 ? "+" : ""}${r.pct.toFixed(2)}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}
