import LiveConvergenceChart from "../charts/LiveConvergenceChart";

/** Biểu đồ hội tụ giá THẬT 30 ngày các sàn quốc tế (đã bỏ card cảnh báo mẫu). */
export default function ConvergenceAndAlerts() {
  return (
    <div className="card" id="sec-hoitu">
      <div className="card-head">
        <div>
          <h3>Diễn biến giá các sàn quốc tế · 30 ngày gần nhất</h3>
          <div className="sub">OSE · SHFE · SGX · MRB (USD/tấn, đã quy đổi)</div>
        </div>
        <span className="chip">Dữ liệu thật</span>
      </div>
      <div className="chart-wrap">
        <LiveConvergenceChart />
      </div>
    </div>
  );
}
