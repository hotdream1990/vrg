/* Mục 5 — Đề xuất mua từ khách hàng - hàng VRG: số lượng (tấn) + đơn giá (VNĐ/tấn) theo chủng loại.
   Chỉ lưu trong phiếu (không mirror sang chuỗi giá). */

import { type ProposalSection } from "../../../../lib/market-quote-client";
import NumInput from "../../sections/NumInput";

type Props = {
  grades: string[];
  section: ProposalSection;
  readOnly?: boolean;
  prevQty?: Record<string, number | null>;
  prevPrices?: Record<string, number | null>;
  onQty: (grade: string, v: number | null) => void;
  onPrice: (grade: string, v: number | null) => void;
  onNote: (v: string) => void;
};

export default function ProposalTable({ grades, section, readOnly, prevQty, prevPrices, onQty, onPrice, onNote }: Props) {
  return (
    <div className="card blt-section blt-editable" style={{ marginBottom: 16 }}>
      <div className="blt-section-header">
        <h3>5. Đề xuất mua từ khách hàng - Hàng VRG</h3>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>số lượng (tấn) · đơn giá (VNĐ/tấn)</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Chủng loại</th>
            <th className="r">Số lượng (tấn)</th>
            <th className="r">Đơn giá (Đồng/tấn)</th>
          </tr>
        </thead>
        <tbody>
          {grades.map((g) => (
            <tr key={g}>
              <td style={{ fontWeight: 500 }}>{g}</td>
              <td className="r">
                <NumInput value={section.qty?.[g] ?? null} readOnly={readOnly}
                  prevValue={prevQty?.[g]} onChange={(v) => onQty(g, v)} />
              </td>
              <td className="r">
                <NumInput value={section.prices?.[g] ?? null} readOnly={readOnly}
                  prevValue={prevPrices?.[g]} onChange={(v) => onPrice(g, v)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <label className="blt-date-label" style={{ display: "block", marginTop: 12 }}>Ghi chú / Thông tin
        <textarea className="blt-date-input" style={{ width: "100%", minHeight: 52, resize: "vertical" }}
          value={section.note} readOnly={readOnly} placeholder="Ghi chú đề xuất từ khách hàng…"
          onChange={(e) => onNote(e.target.value)} />
      </label>
    </div>
  );
}
