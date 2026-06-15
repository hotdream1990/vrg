import { forecastFrames, scenarios } from "../../../data/sample-data";
import ForecastChart from "../charts/ForecastChart";

/** Ma trận kịch bản Bull/Base/Bear + dự báo đa khung thời gian. */
export default function ScenarioAndForecast() {
  return (
    <div className="grid-2" id="sec-kichban">
      <div className="card">
        <div className="card-head">
          <h3>⌖ Ma trận Kịch bản Chiến lược · Tuần 21/2026</h3>
          <span className="chip">AI đề xuất</span>
        </div>
        <div className="scenario">
          {scenarios.map((s) => (
            <div className={`sc ${s.kind}`} key={s.kind}>
              <h4>
                {s.title} <span style={{ fontSize: 11 }}>{s.arrow}</span>
              </h4>
              <div className="prob">{s.prob}</div>
              <div className="range">{s.range}</div>
              <div className="signals">{s.signals}</div>
              <div className="reco">{s.reco}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h3>⧗ Dự báo Đa khung thời gian</h3>
          <span className="chip info">Rolling Forecast</span>
        </div>
        <div className="chart-wrap">
          <ForecastChart />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 8, marginTop: 10, fontSize: 12 }}>
          {forecastFrames.map((f) => (
            <div key={f.title} style={{ padding: 8, background: "#0d1428", borderRadius: 8, borderLeft: `3px solid ${f.color}` }}>
              <b>{f.title}</b>
              <br />
              <span style={{ color: "var(--muted)" }}>{f.desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
