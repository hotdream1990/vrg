import { useEffect, useState } from "react";

import { dm } from "../../../../lib/date";
import { getQuote, listQuotes } from "../../../../lib/market-quote-client";
import GradeBarChart from "../../charts/GradeBarChart";

const vnum = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 0 });

/** Giá mủ chén thu mua (mục 6 của phiếu báo giá) — mức mới nhất theo đơn vị. */
export default function CupLatexBlock() {
  const [bars, setBars] = useState<{ labels: string[]; values: number[] } | null>(null);
  const [caption, setCaption] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const list = await listQuotes();
        if (!list.length) { setBars({ labels: [], values: [] }); return; }
        const q = await getQuote(list[0].as_of);
        const entries = Object.entries(q.regions_cup ?? {}).filter(([, v]) => v != null) as [string, number][];
        setBars({ labels: entries.map((e) => e[0]), values: entries.map((e) => e[1]) });
        if (entries.length) {
          const vals = entries.map((e) => e[1]);
          setCaption(`Ngày ${dm(list[0].as_of)}: ${vnum(Math.min(...vals))}–${vnum(Math.max(...vals))} đ/kg · ${entries.length} đơn vị.`);
        } else setCaption(`Phiếu ${dm(list[0].as_of)} chưa nhập mủ chén.`);
      } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu"); }
    })();
  }, []);

  const ready = !!bars && bars.values.length > 0;
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3 className={ready ? undefined : "title-demo"}>Giá mủ chén (thu mua nội địa)</h3>
          {caption && <div className="sub">{caption}</div>}
        </div>
        <span className={`chip ${ready ? "" : "demo"}`}>{ready ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
      </div>
      {err ? <div className="scan-empty">{err}</div>
        : !bars ? <div className="scan-empty">Đang tải…</div>
        : !ready ? <div className="scan-empty">Phiếu gần nhất chưa nhập mủ chén.</div>
        : <div className="chart-wrap"><GradeBarChart labels={bars.labels} values={bars.values} color="#a855f7" unit="đ/kg" /></div>}
    </div>
  );
}
