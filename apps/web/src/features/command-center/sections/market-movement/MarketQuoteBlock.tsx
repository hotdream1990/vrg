import { useEffect, useState } from "react";

import { dmy } from "../../../../lib/date";
import { type MarketQuote, getQuote, listQuotes } from "../../../../lib/market-quote-client";

const mil = (v: number | null) => (v == null ? "—" : (v / 1e6).toLocaleString("vi-VN", { maximumFractionDigits: 1 }));
const usd = (v: number | null) => (v == null ? "—" : v.toLocaleString("vi-VN", { maximumFractionDigits: 0 }));
const chgColor = (p: number | null) => (p == null ? "#5f6f67" : p > 0 ? "#0b7a3b" : p < 0 ? "#c0392b" : "#5f6f67");

function gradesOf(q: MarketQuote): string[] {
  const secs = [q.domestic_private, q.domestic_export, q.export_vrg, q.domestic_vrg];
  const seen = new Set<string>(), out: string[] = [];
  for (const s of secs) {
    for (const g of Object.keys(s?.prices ?? {})) {
      if (seen.has(g)) continue;
      seen.add(g);
      if (secs.some((x) => x?.prices?.[g] != null)) out.push(g); // bỏ chủng loại rỗng toàn bộ
    }
  }
  return out;
}

/** Báo giá mủ thị trường — 4 mục giá SVR (NĐ tư nhân · NĐ hàng XK · XK VRG · NĐ VRG) + tình trạng,
 *  lấy phiếu gần nhất; cột XK VRG kèm %thay đổi so phiếu trước. */
export default function MarketQuoteBlock() {
  const [q, setQ] = useState<MarketQuote | null>(null);
  const [prev, setPrev] = useState<MarketQuote | null>(null);
  const [meta, setMeta] = useState<{ cur: string; prev: string | null } | null>(null);
  const [err, setErr] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const list = (await listQuotes()).filter((s) => s.filled > 0);
        if (!list.length) { setLoaded(true); return; }
        const cur = list[0].as_of, pv = list[1]?.as_of ?? null;
        const [c, p] = await Promise.all([getQuote(cur), pv ? getQuote(pv) : Promise.resolve(null)]);
        setQ(c); setPrev(p); setMeta({ cur, prev: pv }); setLoaded(true);
      } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu"); setLoaded(true); }
    })();
  }, []);

  const ready = !!q;
  const grades = q ? gradesOf(q) : [];
  return (
    <div className="card" style={{ marginBottom: 18 }} id="sec-baogia">
      <div className="card-head">
        <div>
          <h3 className={ready ? undefined : "title-demo"}>Báo giá mủ thị trường · giá SVR các mục</h3>
          {meta && <div className="sub">Phiếu {dmy(meta.cur)}{meta.prev ? ` · cột XK VRG so phiếu ${dmy(meta.prev)}` : ""} — NĐ theo triệu đồng/tấn, XK theo USD/tấn</div>}
        </div>
        <span className={`chip ${ready ? "" : "demo"}`}>{ready ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
      </div>
      {err ? <div className="scan-empty">{err}</div>
        : !loaded ? <div className="scan-empty">Đang tải…</div>
        : !ready ? <div className="scan-empty">Chưa có phiếu báo giá nào có số liệu.</div>
        : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Chủng loại</th>
                  <th className="r">NĐ tư nhân<br /><small style={{ color: "var(--muted)" }}>tr.đ/tấn</small></th>
                  <th className="r">NĐ hàng XK<br /><small style={{ color: "var(--muted)" }}>tr.đ/tấn</small></th>
                  <th className="r">XK VRG<br /><small style={{ color: "var(--muted)" }}>USD/tấn</small></th>
                  <th className="r">± XK</th>
                  <th className="r">NĐ VRG<br /><small style={{ color: "var(--muted)" }}>tr.đ/tấn</small></th>
                  <th>Tình trạng</th>
                </tr>
              </thead>
              <tbody>
                {grades.map((g) => {
                  const xk = q!.export_vrg.prices?.[g] ?? null;
                  const xkp = prev?.export_vrg.prices?.[g] ?? null;
                  const chg = xk != null && xkp != null && xkp ? ((xk - xkp) / xkp) * 100 : null;
                  const st = q!.domestic_vrg.status?.[g];
                  return (
                    <tr key={g}>
                      <td style={{ fontWeight: 500 }}>{g}</td>
                      <td className="r">{mil(q!.domestic_private.prices?.[g] ?? null)}</td>
                      <td className="r">{mil(q!.domestic_export.prices?.[g] ?? null)}</td>
                      <td className="r">{usd(xk)}</td>
                      <td className="r" style={{ fontWeight: 600, color: chgColor(chg) }}>
                        {chg == null ? "—" : `${chg >= 0 ? "+" : ""}${chg.toFixed(1)}%`}
                      </td>
                      <td className="r">{mil(q!.domestic_vrg.prices?.[g] ?? null)}</td>
                      <td>{st ? <span className="chip">{st}</span> : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}
