import { alerts } from "../../../data/sample-data";
import PriceLineChart from "../charts/PriceLineChart";

/** Hội tụ 4 sàn: biểu đồ 30 ngày (trái) + cảnh báo thông minh (phải). */
export default function ConvergenceAndAlerts() {
  return (
    <div className="grid" id="sec-hoitu">
      <div className="card">
        <div className="card-head">
          <div>
            <h3>Diễn biến giá 4 sàn quốc tế · 30 ngày gần nhất</h3>
            <div className="sub">TOCOM (OSE) · SHANGHAI · SGX · MRE · USD/tấn</div>
          </div>
          <span className="chip">Auto-refresh 60s</span>
        </div>
        <div className="chart-wrap">
          <PriceLineChart />
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h3>⚠ Cảnh báo thông minh</h3>
          <span className="chip warn">3 mới</span>
        </div>
        {alerts.map((a) => (
          <div className={`alert ${a.kind}`} key={a.title}>
            <div className="ico">{a.ico}</div>
            <div className="body">
              <b>{a.title}</b>
              <span>{a.desc}</span>
            </div>
            <div className="time">{a.time}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
