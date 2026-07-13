import { useEffect, useState } from "react";

import { fetchPurchaseSheet } from "../../../../lib/api-client";
import { dm } from "../../../../lib/date";
import MinMaxBandChart from "../../charts/MinMaxBandChart";

const vnum = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
const WINDOW_DAYS = 30; // cửa sổ hiển thị gần nhất cho dễ đọc

type Band = { labels: string[]; min: number[]; max: number[]; avg: number[] };

/** Giá mủ nước thu mua nội địa — dải min–max theo ngày (thấy rõ chênh lệch giữa các đơn vị). */
export default function RawLatexBlock() {
  const [band, setBand] = useState<Band | null>(null);
  const [caption, setCaption] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    fetchPurchaseSheet().then((p) => {
      // Ngày cũ → mới; mỗi ngày gom min/max/TB qua các đơn vị; giữ cửa sổ gần nhất.
      const days = [...p.dates].sort().slice(-WINDOW_DAYS);
      const rows = days
        .map((d) => ({ d, vals: p.companies.map((c) => p.values[c]?.[d]).filter((v): v is number => v != null) }))
        .filter((r) => r.vals.length > 0);
      if (!rows.length) { setBand({ labels: [], min: [], max: [], avg: [] }); return; }
      setBand({
        labels: rows.map((r) => dm(r.d)),
        min: rows.map((r) => Math.min(...r.vals)),
        max: rows.map((r) => Math.max(...r.vals)),
        avg: rows.map((r) => r.vals.reduce((s, x) => s + x, 0) / r.vals.length),
      });
      const last = rows[rows.length - 1];
      const avg = last.vals.reduce((s, x) => s + x, 0) / last.vals.length;
      setCaption(`Ngày ${dm(last.d)}: ${vnum(Math.min(...last.vals))}–${vnum(Math.max(...last.vals))} đ/độ TSC · TB ${vnum(avg)} · ${last.vals.length} đơn vị.`);
    }).catch((e) => setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu"));
  }, []);

  const ready = !!band && band.labels.length > 0;
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
        : !band ? <div className="scan-empty">Đang tải…</div>
        : !ready ? <div className="scan-empty">Chưa có giá mủ nước.</div>
        : <div className="chart-wrap"><MinMaxBandChart labels={band.labels} min={band.min} max={band.max} avg={band.avg} color="#16AF67" unit="đ/độ TSC" /></div>}
    </div>
  );
}
