import { kpis } from "../../../data/sample-data";

/** Hàng 4 thẻ KPI giá chủ lực (RSS3/SMR20/LATEX/Mủ nước). */
export default function KpiRow() {
  return (
    <div className="kpi-row">
      {kpis.map((k) => (
        <div className="kpi" key={k.label}>
          <div className="label">{k.label}</div>
          <div className="value">{k.value}</div>
          <span className={`delta ${k.delta}`}>{k.deltaText}</span>
          <div className="sub">{k.sub}</div>
        </div>
      ))}
    </div>
  );
}
