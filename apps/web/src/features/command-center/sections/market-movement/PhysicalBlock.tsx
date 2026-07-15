import { useEffect, useState } from "react";

import { fetchPhysicalSheet } from "../../../../lib/api-client";
import { dm, dmy } from "../../../../lib/date";
import MultiLineChart from "../../charts/MultiLineChart";

type Chart = { labels: string[]; series: { name: string; values: (number | null)[] }[] };
const vnum = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
const daysAgoISO = (n: number) => new Date(Date.now() - n * 86400000).toISOString().slice(0, 10);

/** Giá physical (Reuters, giao ngay) — diễn biến 30 ngày các chủng loại, USD/tấn. */
export default function PhysicalBlock() {
  const [data, setData] = useState<Chart | null>(null);
  const [caption, setCaption] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    fetchPhysicalSheet(daysAgoISO(30)).then((ph) => {
      if (!ph.dates.length) { setData({ labels: [], series: [] }); return; }
      const dates = [...ph.dates].sort();                 // ASC cho trục thời gian
      const labels = dates.map(dm);
      const series = ph.grades
        .map((g) => ({ name: g, values: dates.map((d) => ph.values[g]?.[d] ?? null) }))
        .filter((s) => s.values.some((v) => v != null));
      setData({ labels, series });

      const cur = ph.dates[0], prev = ph.dates[1] ?? null;
      const rss3 = ph.values["RSS3"]?.[cur];
      setCaption(
        `Reuters · phiên ${dmy(cur)}${prev ? ` (so ${dm(prev)})` : ""} · USD/tấn`
        + (rss3 != null ? ` · RSS3 ${vnum(rss3)}` : ""),
      );
    }).catch((e) => setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu"));
  }, []);

  const ready = !!data && data.series.length > 0;
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3 className={ready ? undefined : "title-demo"}>Giá Physical (giao ngay) · 30 ngày</h3>
          {caption && <div className="sub">{caption}</div>}
        </div>
        <span className={`chip ${ready ? "" : "demo"}`}>{ready ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
      </div>
      {err ? <div className="scan-empty">{err}</div>
        : !data ? <div className="scan-empty">Đang tải…</div>
        : !ready ? <div className="scan-empty">Chưa có giá physical.</div>
        : <div className="chart-wrap"><MultiLineChart labels={data.labels} series={data.series} /></div>}
    </div>
  );
}
