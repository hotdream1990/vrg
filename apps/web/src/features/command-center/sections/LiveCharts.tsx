import GradeBarChart from "../charts/GradeBarChart";
import HistoryLineChart from "../charts/HistoryLineChart";

type Point = { as_of: string; price: number };

export type ChartsData = {
  shfe: Point[];
  rss3: Point[];
  tsr20: Point[];
  fxCny: Point[];
  physLabels: string[];
  physValues: number[];
};

/** Khu biểu đồ THẬT: 4 đường settlement/tỷ giá (lịch sử) + 1 cột physical theo grade. */
export default function LiveCharts({ shfe, rss3, tsr20, fxCny, physLabels, physValues }: ChartsData) {
  return (
    <>
      <div className="grid-2">
        <LineCard title="SHFE · Cao su thiên nhiên" sub={`Settlement max-volume · CNY/tấn · ${shfe.length} phiên`} points={shfe} label="SHFE RU (CNY/tấn)" color="#38bdf8" />
        <LineCard title="OSE/TOCOM · RSS3" sub={`Settlement max trading value · JPY/kg · ${rss3.length} phiên`} points={rss3} label="OSE RSS3 (JPY/kg)" color="#22c55e" />
      </div>
      <div className="grid-2">
        <LineCard title="OSE/TOCOM · TSR20" sub={`Settlement · JPY/kg · ${tsr20.length} phiên`} points={tsr20} label="OSE TSR20 (JPY/kg)" color="#a78bfa" />
        <LineCard title="Vĩ mô · USD/CNY" sub={`ECB qua frankfurter · ${fxCny.length} phiên`} points={fxCny} label="USD/CNY" color="#fbbf24" />
      </div>
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="card-head">
          <div>
            <h3>LGM · Physical theo grade (hiện tại)</h3>
            <div className="sub">US cents/kg · {physLabels.length} grade</div>
          </div>
          <span className="chip">Dữ liệu thật</span>
        </div>
        <div className="chart-wrap small">
          {physValues.length > 0 ? (
            <GradeBarChart labels={physLabels} values={physValues} color="#16a34a" />
          ) : (
            <div className="scan-empty">Chưa có data LGM — bấm “Quét giá ngay”.</div>
          )}
        </div>
      </div>
    </>
  );
}

function LineCard({ title, sub, points, label, color }: { title: string; sub: string; points: Point[]; label: string; color: string }) {
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3>{title}</h3>
          <div className="sub">{sub}</div>
        </div>
        <span className="chip">Dữ liệu thật</span>
      </div>
      <div className="chart-wrap">
        {points.length > 0 ? (
          <HistoryLineChart points={points} label={label} color={color} />
        ) : (
          <div className="scan-empty">Chưa có lịch sử — bấm “Nạp lịch sử”.</div>
        )}
      </div>
    </div>
  );
}
