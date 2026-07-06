/* Bảng giá theo chủng loại SVR (Mục 1-3 của phiếu Báo giá mủ). Có cột Tình trạng cho Mục 3. */

import { AutoComplete } from "antd";

import { MARKET_STATUS_OPTIONS, type DomesticVrgSection, type Section } from "../../../../lib/market-quote-client";
import NumInput from "../../sections/NumInput";

const STATUS_OPTS = MARKET_STATUS_OPTIONS.map((s) => ({ value: s }));

type Props = {
  title: string;
  subtitle: string;
  grades: string[];
  section: Section | DomesticVrgSection;
  unitLabel: string;
  withStatus?: boolean;
  readOnly?: boolean;
  onPrice: (grade: string, v: number | null) => void;
  onStatus?: (grade: string, v: string) => void;
  onNote: (v: string) => void;
};

export default function GradePriceTable({
  title, subtitle, grades, section, unitLabel, withStatus, readOnly, onPrice, onStatus, onNote,
}: Props) {
  const status = (section as DomesticVrgSection).status ?? {};
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
            <th className="r">Đơn giá ({unitLabel})</th>
            {withStatus && <th>Tình trạng</th>}
          </tr>
        </thead>
        <tbody>
          {grades.map((g) => (
            <tr key={g}>
              <td style={{ fontWeight: 500 }}>{g}</td>
              <td className="r">
                <NumInput value={section.prices[g] ?? null} readOnly={readOnly}
                  onChange={(v) => onPrice(g, v)} />
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
