import { alerts } from "../../../data/sample-data";
import LiveConvergenceChart from "../charts/LiveConvergenceChart";

/** Hội tụ sàn: biểu đồ giá thật 30 ngày (trái) + cảnh báo thông minh — dữ liệu mẫu (phải). */
export default function ConvergenceAndAlerts() {
  return (
    <div className="grid" id="sec-hoitu">
      <div className="card">
        <div className="card-head">
          <div>
            <h3>Diễn biến giá các sàn quốc tế · 30 ngày gần nhất</h3>
            <div className="sub">OSE · SHANGHAI · MRB (USD/tấn, đã quy đổi) — SGX chưa có nguồn</div>
          </div>
          <span className="chip">Dữ liệu thật</span>
        </div>
        <div className="chart-wrap">
          <LiveConvergenceChart />
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h3 className="title-demo">Cảnh báo thông minh</h3>
          <span className="chip demo">Dữ liệu mẫu</span>
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
