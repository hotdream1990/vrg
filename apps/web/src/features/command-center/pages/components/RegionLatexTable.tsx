/* Mục 6 — Giá mủ khu vực theo đơn vị: mủ nước (đồng/độ TSC) + mủ chén (đồng/độ DRC).
   Đồng bộ kho "Giá mủ nguyên liệu" (mủ nước → purchase, mủ chén → purchase_cup). */

import { SyncOutlined } from "@ant-design/icons";

import NumInput from "../../sections/NumInput";
import { CUP_PRICE_UNIT, LATEX_PRICE_UNIT } from "../../../../lib/purchase-price-unit";

type Props = {
  units: string[];
  regions: Record<string, number | null>; // mủ nước
  regionsCup: Record<string, number | null>; // mủ chén
  readOnly?: boolean;
  /** Đơn vị đang bật "tự động lấy số từ đơn vị" → dòng đó chỉ xem (số do đơn vị tự khai). */
  autoUnits?: Set<string>;
  prevRegions?: Record<string, number | null>;
  prevRegionsCup?: Record<string, number | null>;
  onPrice: (unit: string, v: number | null) => void;
  onPriceCup: (unit: string, v: number | null) => void;
};

export default function RegionLatexTable({
  units, regions, regionsCup, readOnly, autoUnits, prevRegions, prevRegionsCup, onPrice, onPriceCup,
}: Props) {
  const isAuto = (u: string) => !!autoUnits?.has(u);
  return (
    <div className="card blt-section blt-editable" style={{ marginBottom: 16 }}>
      <div className="blt-section-header">
        <h3>6. Giá mủ khu vực</h3>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          mủ nước ({LATEX_PRICE_UNIT}) · mủ chén ({CUP_PRICE_UNIT}) · đồng bộ với trang "Giá mủ nguyên liệu"
          {autoUnits?.size ? " · dòng có dấu đồng bộ là số đơn vị tự khai (chỉ xem)" : ""}
        </span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Đơn vị / khu vực</th>
            <th className="r">Giá mủ nước ({LATEX_PRICE_UNIT})</th>
            <th className="r">Giá mủ chén ({CUP_PRICE_UNIT})</th>
          </tr>
        </thead>
        <tbody>
          {units.map((u) => (
            <tr key={u}>
              <td style={{ fontWeight: 500 }}>
                {isAuto(u) && (
                  <SyncOutlined style={{ marginRight: 6, color: "var(--muted)" }}
                    title="Đang lấy số tự động từ đơn vị — dòng này chỉ xem" />
                )}
                {u}
              </td>
              <td className="r">
                <NumInput value={regions?.[u] ?? null} readOnly={readOnly || isAuto(u)}
                  prevValue={prevRegions?.[u]} onChange={(v) => onPrice(u, v)} />
              </td>
              <td className="r">
                <NumInput value={regionsCup?.[u] ?? null} readOnly={readOnly || isAuto(u)}
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
