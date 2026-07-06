/* Mục 4 — Giá mủ nước theo đơn vị (đồng/độ TSC). Đồng bộ kho "Giá mủ nguyên liệu". */

import NumInput from "../../sections/NumInput";

type Props = {
  units: string[];
  regions: Record<string, number | null>;
  readOnly?: boolean;
  onPrice: (unit: string, v: number | null) => void;
};

export default function RegionLatexTable({ units, regions, readOnly, onPrice }: Props) {
  return (
    <div className="card blt-section blt-editable" style={{ marginBottom: 16 }}>
      <div className="blt-section-header">
        <h3>4. Giá mủ nước các khu vực</h3>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          đồng/độ TSC · đồng bộ với trang "Giá mủ nguyên liệu"
        </span>
      </div>
      <table>
        <thead>
          <tr><th>Đơn vị / khu vực</th><th className="r">Giá mủ nước (đồng/TSC)</th></tr>
        </thead>
        <tbody>
          {units.map((u) => (
            <tr key={u}>
              <td style={{ fontWeight: 500 }}>{u}</td>
              <td className="r">
                <NumInput value={regions[u] ?? null} readOnly={readOnly}
                  onChange={(v) => onPrice(u, v)} />
              </td>
            </tr>
          ))}
          {units.length === 0 && (
            <tr><td colSpan={2} style={{ textAlign: "center", color: "var(--muted)", padding: 16 }}>
              Chưa có đơn vị thành viên — thêm ở trang "Đơn vị thành viên".
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
