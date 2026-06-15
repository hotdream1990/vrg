import { heatmap, vrgRows } from "../../../data/sample-data-panels";

/** Heatmap % thay đổi (sàn × sản phẩm) + bảng so giá sàn VRG vs thị trường. */
export default function HeatmapAndVrg() {
  return (
    <div className="grid-2" id="sec-giasan">
      <div className="card">
        <div className="card-head">
          <h3>⊞ Heatmap · % Thay đổi theo sàn × sản phẩm</h3>
          <span className="chip">Tuần 20/2026</span>
        </div>
        <div className="heatmap">
          <div className="hm-head" />
          {heatmap.cols.map((c) => (
            <div className="hm-head" key={c}>{c}</div>
          ))}
          {heatmap.rows.map((row) => (
            <Row key={row.label} label={row.label} cells={row.cells} />
          ))}
        </div>
        <p style={{ color: "var(--muted)", fontSize: 11, margin: "12px 0 0" }}>
          Màu sậm hơn = mức tăng/giảm lớn hơn. Click vào ô để xem chi tiết phiên giao dịch.
        </p>
      </div>

      <div className="card">
        <div className="card-head">
          <h3>⊜ So sánh Giá sàn Tập đoàn vs Thị trường</h3>
          <span className="chip warn">Gợi ý điều chỉnh</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Sản phẩm</th><th>Giá sàn VRG</th><th>Giá TT (giao ngay)</th><th>Chênh lệch</th><th>AI gợi ý</th>
            </tr>
          </thead>
          <tbody>
            {vrgRows.map((r) => (
              <tr key={r.product}>
                <td>{r.product}</td>
                <td>{r.vrg}</td>
                <td>{r.market}</td>
                <td className={r.diffCls}>{r.diff}</td>
                <td><span className={r.chipCls}>{r.chip}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Row({ label, cells }: { label: string; cells: { text: string; bg: string; color: string }[] }) {
  return (
    <>
      <div className="hm-label">{label}</div>
      {cells.map((c, i) => (
        <div className="hm-cell" key={i} style={{ background: c.bg, color: c.color }}>{c.text}</div>
      ))}
    </>
  );
}
