import { useMemo, useState } from "react";

import type { MqHistorySection } from "../../../../lib/market-quote-client";
import MultiLineChart from "../../charts/MultiLineChart";

const PALETTE = ["#16AF67", "#2563eb", "#a855f7", "#f59e0b", "#ef4444", "#0891b2", "#db2777", "#0d9488"];

/** 1 box lịch sử cho 1 mục (NĐ tư nhân / XK VRG / …): chip bật/tắt từng chủng loại + Hiện/Ẩn hết.
 *  Màu đường cố định theo chủng loại (không đổi khi ẩn bớt). VNĐ quy về triệu đồng cho trục dễ đọc. */
export default function HistorySectionChart({ section }: { section: MqHistorySection }) {
  const grades = section.series.map((s) => s.name);
  const colorOf = (g: string) => PALETTE[Math.max(0, grades.indexOf(g)) % PALETTE.length];
  const [visible, setVisible] = useState<Set<string>>(() => new Set(grades));

  const isVnd = section.unit.includes("VNĐ");
  const chart = useMemo(() => {
    const scale = isVnd ? 1e6 : 1;
    return {
      labels: section.labels,
      series: section.series
        .filter((s) => visible.has(s.name))
        .map((s) => ({ name: s.name, color: colorOf(s.name), values: s.values.map((v) => (v == null ? null : v / scale)) })),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section, visible, isVnd]);

  const toggle = (g: string) => setVisible((prev) => {
    const n = new Set(prev);
    n.has(g) ? n.delete(g) : n.add(g);
    return n;
  });

  const empty = grades.length === 0;
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3 className={empty ? "title-demo" : undefined}>{section.label}</h3>
          <div className="sub">Lịch sử theo phiên · {isVnd ? "triệu đồng/tấn" : section.unit} · {section.labels.length} phiên</div>
        </div>
      </div>
      {empty ? (
        <div className="scan-empty">Chưa có dữ liệu lịch sử cho mục này.</div>
      ) : (
        <>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center", marginBottom: 10 }}>
            {grades.map((g) => {
              const on = visible.has(g), col = colorOf(g);
              return (
                <button key={g} onClick={() => toggle(g)} title={on ? "Bấm để ẩn" : "Bấm để hiện"}
                  style={{
                    fontSize: 11, padding: "2px 9px", borderRadius: 12, cursor: "pointer", lineHeight: 1.6,
                    border: `1px solid ${on ? col : "var(--line)"}`,
                    background: on ? `${col}22` : "transparent",
                    color: on ? col : "var(--muted)", fontWeight: on ? 600 : 400,
                    textDecoration: on ? "none" : "line-through",
                  }}>
                  {g}
                </button>
              );
            })}
            <span style={{ flex: 1 }} />
            <button className="link-btn" onClick={() => setVisible(new Set(grades))}
              style={{ fontSize: 11, color: "var(--accent-2)", background: "none", border: "none", cursor: "pointer" }}>Hiện hết</button>
            <button className="link-btn" onClick={() => setVisible(new Set())}
              style={{ fontSize: 11, color: "var(--muted)", background: "none", border: "none", cursor: "pointer" }}>Ẩn hết</button>
          </div>
          <div className="chart-wrap small">
            {chart.series.length === 0
              ? <div className="scan-empty" style={{ height: "100%", display: "grid", placeItems: "center" }}>Đã ẩn hết — bấm "Hiện hết".</div>
              : <MultiLineChart labels={chart.labels} series={chart.series} legend={false} />}
          </div>
        </>
      )}
    </div>
  );
}
