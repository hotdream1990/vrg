import { useEffect, useState } from "react";

import { fetchPurchaseSheet } from "../../../../lib/api-client";
import GradeBarChart from "../../charts/GradeBarChart";

const vnum = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 0 });

/** Giá mủ nước thu mua nội địa — mức mới nhất theo từng đơn vị (cột). */
export default function RawLatexBlock() {
  const [bars, setBars] = useState<{ labels: string[]; values: number[] } | null>(null);
  const [caption, setCaption] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    fetchPurchaseSheet().then((p) => {
      if (!p.dates.length || !p.companies.length) { setBars({ labels: [], values: [] }); return; }
      const cur = p.dates[0];
      const entries = p.companies
        .map((c) => ({ c, v: p.values[c]?.[cur] }))
        .filter((e): e is { c: string; v: number } => e.v != null);
      setBars({ labels: entries.map((e) => e.c), values: entries.map((e) => e.v) });
      if (entries.length) {
        const vals = entries.map((e) => e.v);
        const avg = vals.reduce((s, x) => s + x, 0) / vals.length;
        setCaption(`Ngày ${cur.slice(5)}: ${vnum(Math.min(...vals))}–${vnum(Math.max(...vals))} đ/độ TSC · TB ${vnum(avg)} · ${entries.length} đơn vị.`);
      }
    }).catch((e) => setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu"));
  }, []);

  const ready = !!bars && bars.values.length > 0;
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3 className={ready ? undefined : "title-demo"}>Giá mủ nước (thu mua nội địa)</h3>
          {caption && <div className="sub">{caption}</div>}
        </div>
        <span className={`chip ${ready ? "" : "demo"}`}>{ready ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
      </div>
      {err ? <div className="scan-empty">{err}</div>
        : !bars ? <div className="scan-empty">Đang tải…</div>
        : !ready ? <div className="scan-empty">Chưa có giá mủ nước.</div>
        : <div className="chart-wrap"><GradeBarChart labels={bars.labels} values={bars.values} color="#16AF67" unit="đ/độ TSC" /></div>}
    </div>
  );
}
