import { Select } from "antd";
import { useEffect, useMemo, useState } from "react";

import { type MqPriceHistory, fetchMarketPriceHistory } from "../../../../lib/market-quote-client";
import MultiLineChart from "../../charts/MultiLineChart";

/** Lịch sử giá SVR thị trường theo thời gian — chọn mục (NĐ tư nhân / NĐ hàng XK / XK VRG / NĐ VRG),
 *  vẽ đường xu hướng từng chủng loại. Giá VNĐ quy về triệu đồng để trục dễ đọc. */
export default function MarketHistoryBlock() {
  const [data, setData] = useState<MqPriceHistory | null>(null);
  const [sel, setSel] = useState("export_vrg");
  const [err, setErr] = useState("");

  useEffect(() => {
    fetchMarketPriceHistory(90).then((d) => {
      setData(d);
      const withData = d.sections.find((s) => s.series.length > 0);
      if (withData) setSel(withData.key);
    }).catch((e) => setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu"));
  }, []);

  const sections = data?.sections ?? [];
  const active = sections.find((s) => s.key === sel) ?? sections[0];
  const isVnd = !!active?.unit?.includes("VNĐ");
  const chart = useMemo(() => {
    if (!active) return null;
    const scale = isVnd ? 1e6 : 1;
    return {
      labels: active.labels,
      series: active.series.map((s) => ({ name: s.name, values: s.values.map((v) => (v == null ? null : v / scale)) })),
    };
  }, [active, isVnd]);

  const hasAny = sections.some((s) => s.series.length > 0);
  const ready = !!active && active.series.length > 0;
  return (
    <div className="card" style={{ marginBottom: 18 }} id="sec-lichsu">
      <div className="card-head">
        <div>
          <h3 className={hasAny ? undefined : "title-demo"}>Lịch sử giá thị trường theo mục</h3>
          {active && <div className="sub">{active.label} · {isVnd ? "triệu đồng/tấn" : active.unit} · {active.labels.length} phiên gần nhất</div>}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {sections.length > 0 && (
            <Select
              size="small" value={sel} onChange={setSel} style={{ minWidth: 210 }}
              options={sections.map((s) => ({ value: s.key, label: s.label + (s.series.length ? "" : " (trống)") }))}
            />
          )}
          <span className={`chip ${hasAny ? "" : "demo"}`}>{hasAny ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
        </div>
      </div>
      {err ? <div className="scan-empty">{err}</div>
        : !data ? <div className="scan-empty">Đang tải…</div>
        : !ready ? <div className="scan-empty">Mục này chưa có dữ liệu lịch sử — chọn mục khác hoặc nhập thêm phiếu.</div>
        : <div className="chart-wrap"><MultiLineChart labels={chart!.labels} series={chart!.series} /></div>}
    </div>
  );
}
