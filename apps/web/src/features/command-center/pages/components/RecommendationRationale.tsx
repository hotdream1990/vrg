import { CheckCircleOutlined, WarningOutlined } from "@ant-design/icons";

import type { FloorDriver, SuggestItem } from "../../../../lib/floor-suggest-client";
import { buildRationale } from "../../../../lib/floor-rationale";

type Props = {
  item?: SuggestItem;
  prevAsOf: string | null;
  basketChangePct: number | null;
  drivers: FloorDriver[];
};

/** Diễn giải đề xuất điều chỉnh cho grade đang chọn: khẳng định mức điều chỉnh là hợp lý. */
export default function RecommendationRationale({ item, prevAsOf, basketChangePct, drivers }: Props) {
  if (!item) return null;
  const r = buildRationale(item, { prevAsOf, basketChangePct, drivers });

  if (!r) {
    return (
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Diễn giải đề xuất — {item.grade}</h3>
        <p style={{ color: "var(--muted)", margin: 0 }}>
          Chưa đủ dữ liệu để diễn giải (thiếu giá sàn lần trước hoặc dự báo cho chủng loại này).
        </p>
      </div>
    );
  }

  return (
    <div className="card" style={{ borderLeft: "4px solid var(--accent, #16a34a)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 6 }}>
        <h3 style={{ marginTop: 0, marginBottom: 4 }}>{r.headline}</h3>
        <span style={{ fontSize: 12, color: "var(--muted)" }}>Bấm dòng khác trong bảng để đổi chủng loại</span>
      </div>

      <ul style={{ listStyle: "none", margin: "8px 0 0", padding: 0, lineHeight: 1.7, fontSize: 13.5 }}>
        {r.reasons.map((s, i) => (
          <li key={i} style={{ marginBottom: 6, display: "flex", gap: 8 }}>
            <CheckCircleOutlined style={{ color: "#16a34a", marginTop: 4, flexShrink: 0 }} />
            <span>{s}</span>
          </li>
        ))}
      </ul>

      {r.caution && (
        <div style={{ marginTop: 10, padding: "8px 12px", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 8, fontSize: 13, color: "#9a3412", display: "flex", gap: 8 }}>
          <WarningOutlined style={{ marginTop: 3, flexShrink: 0 }} /><span>{r.caution}</span>
        </div>
      )}

      {drivers.length > 0 && (
        <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 8 }}>
          {drivers.map((d) => (
            <span key={d.index} className="chip" style={{ fontSize: 12 }}>
              {d.index}: {d.change_pct == null ? "—" : (d.change_pct > 0 ? "+" : "") + d.change_pct + "%"}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
