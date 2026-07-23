import { AimOutlined, FallOutlined, RiseOutlined, SwapOutlined } from "@ant-design/icons";

import type { TrendSuggestion } from "../../../../lib/market-movement-client";

/** Màu + icon theo hướng: tăng = xanh, giảm = đỏ, đi ngang = trung tính (đúng quy ước các bảng khác). */
function look(direction: string) {
  const d = direction.toLowerCase();
  if (d.includes("tăng")) return { color: "#0b7a3b", Icon: RiseOutlined };
  if (d.includes("giảm")) return { color: "#c0392b", Icon: FallOutlined };
  return { color: "var(--muted)", Icon: SwapOutlined };
}

/** Box "Gợi ý xu hướng" — ngay dưới đoạn Tổng thể: hướng ngắn hạn + lý giải + điểm cần theo dõi.
 *  Là gợi ý THAM KHẢO do AI suy từ chính các nhóm số liệu bên dưới, không phải dự báo mô hình. */
export default function TrendBox({ trend }: { trend: TrendSuggestion }) {
  const { color, Icon } = look(trend.direction);

  return (
    <div style={{
      border: "1px solid var(--line)", borderLeft: `3px solid ${color}`, borderRadius: 8,
      padding: "12px 14px", marginBottom: 12, lineHeight: 1.55, color: "var(--text)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
        <b style={{ color: "var(--text)" }}>
          <AimOutlined style={{ marginRight: 6, color: "var(--accent)" }} />Gợi ý xu hướng
        </b>
        {trend.direction && (
          <span style={{
            color, border: `1px solid ${color}55`, borderRadius: 999,
            padding: "1px 10px", fontSize: 12.5, fontWeight: 600, whiteSpace: "nowrap",
          }}>
            <Icon style={{ marginRight: 5 }} />{trend.direction}
          </span>
        )}
        <span style={{ color: "var(--muted)", fontSize: 12 }}>ngắn hạn 1–2 tuần · tham khảo</span>
      </div>

      {trend.outlook && <div>{trend.outlook}</div>}

      {trend.watch.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 4 }}>Cần theo dõi</div>
          <ul style={{ margin: 0, paddingLeft: 18, color: "var(--text)" }}>
            {trend.watch.map((w) => <li key={w} style={{ marginBottom: 2 }}>{w}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
