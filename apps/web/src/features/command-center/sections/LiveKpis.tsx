import { type LatestRow } from "../../../lib/api-client";

// 4 chỉ số đầu báo (mỗi sàn 1 grade tiêu biểu).
const HEADLINE = [
  { source: "shfe", grade: "RU", label: "SHFE · RU (Thượng Hải)" },
  { source: "tocom", grade: "RSS3", label: "OSE · RSS3 (Nhật)" },
  { source: "reuters", grade: "RSS3", label: "Reuters · RSS3 (BKK)" },
  { source: "lgm", grade: "SMR20", label: "MRE · SMR20 (Malaysia)" },
];

/** Hàng KPI giá THẬT mới nhất + % thay đổi so phiên trước (deltas tính từ history). */
export default function LiveKpis({ latest, deltas }: { latest: LatestRow[]; deltas: Record<string, number> }) {
  return (
    <div className="kpi-row">
      {HEADLINE.map((h) => {
        const r = latest.find((x) => x.source === h.source && x.grade === h.grade);
        const d = deltas[`${h.source}:${h.grade}`];
        const dir = d == null ? "flat" : d > 0 ? "up" : d < 0 ? "down" : "flat";
        return (
          <div className="kpi" key={h.label}>
            <div className="label">{h.label}</div>
            <div className="value">{r ? r.price.toLocaleString() : "—"}</div>
            {d != null ? (
              <span className={`delta ${dir}`}>
                {d > 0 ? "▲ +" : d < 0 ? "▼ " : "≈ "}{d.toFixed(2)}%
              </span>
            ) : (
              <span className="delta flat">{r ? r.unit : "chưa có data"}</span>
            )}
            <div className="sub">{r ? `${r.unit} · ${r.price_type} · ${r.as_of}` : "—"}</div>
          </div>
        );
      })}
    </div>
  );
}
