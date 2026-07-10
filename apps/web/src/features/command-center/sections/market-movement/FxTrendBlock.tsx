import { useEffect, useState } from "react";

import { fetchSheet } from "../../../../lib/api-client";
import MultiLineChart from "../../charts/MultiLineChart";

type Chart = { labels: string[]; series: { name: string; values: (number | null)[] }[] };
const PAIRS: [string, string][] = [
  ["USD/VND (Bán)", "USD/VND"], ["USD/MYR", "USD/MYR"], ["USD/JPY", "USD/JPY"], ["USD/CNY", "USD/CNY"],
];
const vnum = (n: number, d = 0) => n.toLocaleString("vi-VN", { maximumFractionDigits: d });

/** Tỷ giá 30 ngày, chuẩn hoá base-100 tại đầu kỳ để so biến động các cặp trên cùng trục. */
export default function FxTrendBlock() {
  const [data, setData] = useState<Chart | null>(null);
  const [caption, setCaption] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    fetchSheet({ days: 30 }).then((sheet) => {
      const rows = [...sheet.rows].sort((a, b) => a.as_of.localeCompare(b.as_of));
      const labels = rows.map((r) => r.as_of.slice(5));
      const series = PAIRS.map(([pair, name]) => {
        const raw = rows.map((r) => r.fx?.[pair] ?? null);
        const base = raw.find((v): v is number => v != null) ?? null;
        return { name, values: base ? raw.map((v) => (v == null ? null : (v / base) * 100)) : raw };
      }).filter((s) => s.values.some((v) => v != null));
      setData({ labels, series });
      const vnd = rows.map((r) => r.fx?.["USD/VND (Bán)"] ?? r.fx?.["USD/VND (Mua)"] ?? null)
        .filter((v): v is number => v != null);
      if (vnd.length) {
        const cur = vnd.at(-1)!, prev = vnd.length >= 2 ? vnd.at(-2)! : null;
        const chg = prev ? ` (${cur - prev >= 0 ? "+" : ""}${(((cur - prev) / prev) * 100).toFixed(2)}%)` : "";
        setCaption(`USD/VND hiện ${vnum(cur)}${chg}. Đường chuẩn hoá 100 tại đầu kỳ để so mức biến động.`);
      }
    }).catch((e) => setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu"));
  }, []);

  const ready = !!data && data.series.length > 0;
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3 className={ready ? undefined : "title-demo"}>Tỷ giá · 30 ngày (chuẩn hoá 100)</h3>
          {caption && <div className="sub">{caption}</div>}
        </div>
        <span className={`chip ${ready ? "" : "demo"}`}>{ready ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
      </div>
      {err ? <div className="scan-empty">{err}</div>
        : !data ? <div className="scan-empty">Đang tải…</div>
        : !ready ? <div className="scan-empty">Chưa có dữ liệu tỷ giá.</div>
        : <div className="chart-wrap"><MultiLineChart labels={data.labels} series={data.series} /></div>}
    </div>
  );
}
