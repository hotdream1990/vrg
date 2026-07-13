/* Bảng giá theo chủng loại SVR (Mục 1-4 của phiếu Báo giá mủ).
   Mỗi chủng loại có: đơn giá · bao bì đóng gói · đơn vị vận chuyển · tình trạng (khi bật withStatus). */

import { AutoComplete, Select } from "antd";

import {
  LATEX_GRADE,
  LATEX_PACKAGING_OPTIONS,
  MARKET_STATUS_OPTIONS,
  PACKAGING_OPTIONS,
  type Section,
} from "../../../../lib/market-quote-client";
import NumInput from "../../sections/NumInput";

const STATUS_OPTS = MARKET_STATUS_OPTIONS.map((s) => ({ value: s }));

type Props = {
  title: string;
  subtitle: string;
  grades: string[];
  section: Section;
  unitLabel: string;
  packagingOptions?: string[];
  withStatus?: boolean;
  readOnly?: boolean;
  prevPrices?: Record<string, number | null>; // giá kỳ trước → cảnh báo lệch ≥10%
  onPrice: (grade: string, v: number | null) => void;
  onPackaging: (grade: string, v: string) => void;
  onShipping: (grade: string, v: string) => void;
  onStatus?: (grade: string, v: string) => void;
  onNote: (v: string) => void;
};

export default function GradePriceTable({
  title, subtitle, grades, section, unitLabel, packagingOptions, withStatus,
  readOnly, prevPrices, onPrice, onPackaging, onShipping, onStatus, onNote,
}: Props) {
  const status = section.status ?? {};
  // Các chủng loại SVR: gợi ý nhập tự do (Hàng rời / Pallet). LATEX: 2 lựa chọn cố định.
  const packOpts = (packagingOptions?.length ? packagingOptions : PACKAGING_OPTIONS).map((s) => ({ value: s }));
  const latexPackOpts = LATEX_PACKAGING_OPTIONS.map((s) => ({ label: s, value: s }));
  return (
    <div className="card blt-section blt-editable" style={{ marginBottom: 16 }}>
      <div className="blt-section-header">
        <h3>{title}</h3>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>{subtitle}</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Chủng loại</th>
            <th>Bao bì đóng gói</th>
            <th>Đơn vị vận chuyển</th>
            {withStatus && <th>Tình trạng</th>}
            <th className="r">Đơn giá ({unitLabel})</th>
          </tr>
        </thead>
        <tbody>
          {grades.map((g) => (
            <tr key={g}>
              <td style={{ fontWeight: 500 }}>{g}</td>
              <td>
                {g === LATEX_GRADE ? (
                  <Select
                    value={section.packaging?.[g] || undefined}
                    options={latexPackOpts}
                    disabled={readOnly}
                    allowClear
                    style={{ width: "100%", minWidth: 150 }}
                    placeholder="Chọn loại bao bì"
                    onChange={(v) => onPackaging(g, v ?? "")}
                  />
                ) : (
                  <AutoComplete
                    value={section.packaging?.[g] ?? ""}
                    options={packOpts}
                    disabled={readOnly}
                    allowClear
                    style={{ width: "100%", minWidth: 130 }}
                    placeholder="Hàng rời / Pallet"
                    onChange={(v) => onPackaging(g, v ?? "")}
                  />
                )}
              </td>
              <td>
                <input className="blt-cell-input" style={{ minWidth: 140 }}
                  value={section.shipping?.[g] ?? ""} readOnly={readOnly}
                  placeholder="Đơn vị vận chuyển…"
                  onChange={(e) => onShipping(g, e.target.value)} />
              </td>
              {withStatus && (
                <td>
                  <AutoComplete
                    value={status[g] ?? ""}
                    options={STATUS_OPTS}
                    disabled={readOnly}
                    allowClear
                    style={{ width: "100%", minWidth: 140 }}
                    placeholder="Chọn hoặc nhập…"
                    filterOption={(input, opt) =>
                      (opt?.value ?? "").toLowerCase().includes(input.toLowerCase())}
                    onChange={(v) => onStatus?.(g, v ?? "")}
                  />
                </td>
              )}
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
          value={section.note} readOnly={readOnly} placeholder="Ghi chú, diễn biến trong ngày…"
          onChange={(e) => onNote(e.target.value)} />
      </label>
    </div>
  );
}
