import { layers, workflow } from "../../../data/sample-data-panels";

/** Kiến trúc 5 lớp lọc Hybrid AI + quy trình hiệp đồng AI–Chuyên gia–Lãnh đạo. */
export default function ArchitectureAndWorkflow() {
  return (
    <div className="grid-2">
      <div className="card">
        <div className="card-head">
          <h3>⌬ Kiến trúc 5 Lớp Lọc · Hybrid AI</h3>
          <span className="chip">On-premise</span>
        </div>
        <div className="layers">
          {layers.map((l) => (
            <div className={`layer l${l.n}`} key={l.n}>
              <div className="pill">{l.pill}</div>
              <div>{l.desc}</div>
              <span className="chip">{l.chip}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h3>⌥ Quy trình Hiệp đồng AI – Chuyên gia – Lãnh đạo</h3>
          <span className="chip info">3 bước</span>
        </div>
        <div style={{ display: "grid", gap: 10 }}>
          {workflow.map((w) => (
            <div key={w.step} style={{ display: "grid", gridTemplateColumns: "48px 1fr", gap: 12, padding: 12, background: "#0d1428", borderRadius: 8, borderLeft: `3px solid ${w.color}` }}>
              <div style={{ width: 36, height: 36, borderRadius: "50%", background: `${w.color}22`, color: w.color, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800 }}>
                {w.step}
              </div>
              <div>
                <b>{w.title}</b>
                <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: 12 }}>{w.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
