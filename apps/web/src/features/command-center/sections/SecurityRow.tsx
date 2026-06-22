import { channels, kpiTargets, security } from "../../../data/sample-data-panels";

/** Hàng cuối: thành trì bảo mật + KPI mục tiêu 12 tháng + kênh cảnh báo. */
export default function SecurityRow() {
  return (
    <div className="grid-3">
      <div className="card">
        <div className="card-head"><h3 className="title-demo">Thành trì Bảo mật</h3><span className="chip demo">Minh hoạ</span></div>
        <div className="sec-grid">
          {security.map((s) => (
            <div className="sec-card" key={s.h4}>
              <div className="ico">{s.ico}</div>
              <h4>{s.h4}</h4>
              <p>{s.p}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="card-head"><h3 className="title-demo">KPI Mục tiêu (12 tháng)</h3><span className="chip demo">Dữ liệu mẫu</span></div>
        <div style={{ display: "grid", gap: 14 }}>
          {kpiTargets.map((k) => (
            <div key={k.label}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                <b>{k.label}</b>
                <span style={{ color: "#0b7a3b" }}>{k.value}</span>
              </div>
              <div style={{ height: 8, background: "var(--panel-2)", borderRadius: 4, overflow: "hidden" }}>
                <div style={{ width: `${k.pct}%`, height: "100%", background: "var(--grad)" }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="card-head"><h3 className="title-demo">Kênh Cảnh báo</h3><span className="chip demo">Minh hoạ</span></div>
        <div style={{ display: "grid", gap: 10 }}>
          {channels.map((c) => (
            <div key={c.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: 10, background: "var(--panel-2)", borderRadius: 8 }}>
              <span>{c.label}</span>
              <span className={c.cls}>{c.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
