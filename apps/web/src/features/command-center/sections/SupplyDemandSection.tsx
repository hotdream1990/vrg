import { tsr20 } from "../../../data/sample-data-panels";
import SupplyDemandChart from "../charts/SupplyDemandChart";

/** Cán cân cung–cầu thế giới 2025–2030 + dự báo giá TSR20 SGX. */
export default function SupplyDemandSection() {
  return (
    <div className="grid-2" id="sec-cungcau">
      <div className="card">
        <div className="card-head">
          <div>
            <h3>▤ Cán cân Cung – Cầu thế giới 2025–2030</h3>
            <div className="sub">Whatnext Rubber · sản xuất vs nhu cầu vs thâm hụt (triệu tấn)</div>
          </div>
          <span className="chip warn">Thâm hụt nới rộng</span>
        </div>
        <div className="chart-wrap">
          <SupplyDemandChart />
        </div>
        <p style={{ color: "var(--muted)", fontSize: 11, margin: "10px 0 0" }}>
          Sản lượng tăng &lt;1%/năm trong khi nhu cầu tăng 2,5–3%/năm — thâm hụt từ 0,86 (2025) lên 2,66 triệu tấn (2030).
          Đây là nền tảng chu kỳ tăng giá 2024–2030.
        </p>
      </div>

      <div className="card">
        <div className="card-head">
          <h3>⟳ Dự báo giá TSR20 · SGX SICOM</h3>
          <span className="chip">USD/tấn</span>
        </div>
        <div style={{ display: "grid", gap: 10 }}>
          <YearCard year="Năm 2025" range={tsr20.y2025} color="#38bdf8" />
          <YearCard year="Năm 2026" range={tsr20.y2026} color="#22c55e" />
          <div style={{ padding: "11px 13px", background: "#16a34a15", borderRadius: 9, border: "1px dashed #16a34a55", fontSize: 12, color: "#cbd5e1" }}>
            {tsr20.note}
          </div>
        </div>
      </div>
    </div>
  );
}

function YearCard({ year, range, color }: { year: string; range: string; color: string }) {
  return (
    <div style={{ padding: 12, background: "#0d1428", borderRadius: 9, borderLeft: `3px solid ${color}` }}>
      <div style={{ fontSize: 12, color: "var(--muted)" }}>{year}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>
        {range} <span style={{ fontSize: 12, color: "var(--muted)" }}>USD/tấn</span>
      </div>
    </div>
  );
}
