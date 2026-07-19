/* Mục 6 — Giá mủ khu vực theo đơn vị: mủ nước + mủ chén (đồng/độ TSC).
   Đồng bộ kho "Giá mủ nguyên liệu" (mủ nước → purchase, mủ chén → purchase_cup). */

import NumInput from "../../sections/NumInput";

type Props = {
  units: string[];
  regions: Record<string, number | null>; // mủ nước
  regionsCup: Record<string, number | null>; // mủ chén
  readOnly?: boolean;
  prevRegions?: Record<string, number | null>;
  prevRegionsCup?: Record<string, number | null>;
  onPrice: (unit: string, v: number | null) => void;
  onPriceCup: (unit: string, v: number | null) => void;
};

export default function RegionLatexTable({
  units, regions, regionsCup, readOnly, prevRegions, prevRegionsCup, onPrice, onPriceCup,
}: Props) {
  return (
    <div className="card blt-section blt-editable" style={{ marginBottom: 16 }}>
      <div className="blt-section-header">
        <h3>6. Giá mủ khu vực</h3>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          mủ nước · mủ chén (đồng/độ TSC) · đồng bộ với trang "Giá mủ nguyên liệu"
        </span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Đơn vị / khu vực</th>
            <th className="r">Giá mủ nước (đồng/độ TSC)</th>
            <th className="r">Giá mủ chén (đồng/độ TSC)</th>
          </tr>
        </thead>
        <tbody>
          {units.map((u) => (
            <tr key={u}>
              <td style={{ fontWeight: 500 }}>{u}</td>
              <td className="r">
                <NumInput value={regions?.[u] ?? null} readOnly={readOnly}
                  prevValue={prevRegions?.[u]} onChange={(v) => onPrice(u, v)} />
              </td>
              <td className="r">
                <NumInput value={regionsCup?.[u] ?? null} readOnly={readOnly}
                  prevValue={prevRegionsCup?.[u]} onChange={(v) => onPriceCup(u, v)} />
              </td>
            </tr>
          ))}
          {units.length === 0 && (
            <tr><td colSpan={3} style={{ textAlign: "center", color: "var(--muted)", padding: 16 }}>
              Chưa có đơn vị thành viên — thêm ở trang "Đơn vị thành viên".
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
