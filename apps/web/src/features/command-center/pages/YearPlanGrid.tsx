/* Bảng nhập Kế hoạch năm ĐẢO (09/10/2026): mỗi chỉ tiêu một hàng, mỗi nhóm một dòng tiêu đề; mỗi đơn vị
   một cột. Ban/admin (> 1 đơn vị): cột "Tổng cộng" đứng NGAY SAU cột nhãn và ghim trái cùng cột nhãn —
   khỏi cuộn qua 60+ cột mới thấy. Dòng tổng chỉ đọc, cộng lại ngay khi gõ từ state (không gọi API).
   HIỆU NĂNG: ~62 đơn vị × 18 ô = 1.100+ InputNumber → ô là `memo` nhận giá trị đơn giản + hàm cố định,
   gõ một ô chỉ vẽ lại ô đó và các ô tổng có số đổi. Rời ô → `onLeave(đơn vị)`. */

import { Fragment, memo, type ReactNode } from "react";

import type { YearPlanRow } from "../../../lib/unit-daily-client";
import { fmtNum } from "../../../lib/unit-daily-fields";
import { numInput, readOnlyBox } from "./unit-daily-inputs";
import YearPlanHelpTip from "./YearPlanHelpTip";
import { ROW_UI, SECTION_HINT, TOTAL_TITLE, TOTAL_TITLE_LEGACY } from "./year-plan-labels";
import {
  PLAN_SECTIONS, PLAN_TOTALS, type PlanSectionRow, sectionRowId, sectionRowValue, sumOrNull, totalInfo,
} from "./year-plan-sections";
import "./year-plan-grid.css";

type PlanKey = keyof YearPlanRow;

type Props = {
  units: string[];
  rowOf: (u: string) => YearPlanRow;
  /** Tham chiếu CỐ ĐỊNH (useCallback) — không thì mọi ô vẽ lại mỗi phím gõ. */
  setCell: (u: string, key: PlanKey, v: number | null) => void;
  cellEditable: (u: string, key: PlanKey) => boolean;
  /** Rời một ô sửa được của đơn vị `u` (lưu các ô đã đổi) — tham chiếu CỐ ĐỊNH. */
  onLeave: (u: string) => void;
  savingUnit: string | null;
  /** Phần thêm dưới tên đơn vị ở tiêu đề cột (trạng thái chốt + «Đề nghị sửa»). */
  unitHeadExtra?: (u: string) => ReactNode;
};

const DIGITS = 3; // tấn tới kg; tỷ đồng tới triệu — đủ, và giấu lỗi số thực của phép cộng
const DIM = { opacity: 0.6 };

/** Ô nhãn của một dòng: tên ngắn · ⓘ gợi ý (nếu có) · đơn vị tính ở mép phải. */
function RowLabel({ row }: { row: PlanSectionRow }) {
  const ui = ROW_UI[sectionRowId(row)];
  return (
    <div className="yp-lab">
      <span className="yp-name">{ui.label}</span>
      {ui.hint && <YearPlanHelpTip text={ui.hint} />}
      <span className="yp-uom">{ui.uom}</span>
    </div>
  );
}

type InputCellProps = {
  unit: string; field: PlanKey; value: number | null; editable: boolean; saving: boolean;
  onChange: Props["setCell"]; onLeave: Props["onLeave"];
};

const InputCell = memo(function InputCell({ unit, field, value, editable, saving, onChange, onLeave }: InputCellProps) {
  return (
    <td style={saving ? DIM : undefined} onBlur={editable ? () => onLeave(unit) : undefined}>
      {numInput(value, (v) => onChange(unit, field, v), !editable)}
    </td>
  );
});

/** Ô tổng của một đơn vị. `fromFallback` = tổng doanh thu đang là SỐ CŨ đã lưu (chưa có mục con). */
const TotalCell = memo(function TotalCell({ value, fromFallback, saving }: { value: number | null; fromFallback: boolean; saving: boolean }) {
  return (
    <td style={saving ? DIM : undefined} title={fromFallback ? TOTAL_TITLE_LEGACY : TOTAL_TITLE}>
      {readOnlyBox(fmtNum(value, DIGITS), fromFallback ? "số cũ" : "tự cộng")}
    </td>
  );
});

export default function YearPlanGrid({
  units, rowOf, setCell, cellEditable, onLeave, savingUnit, unitHeadExtra,
}: Props) {
  const showTotal = units.length > 1;

  const unitCell = (u: string, r: PlanSectionRow) => {
    const saving = savingUnit === u;
    if (r.kind === "total") {
      const { value, fromFallback } = totalInfo(rowOf(u), PLAN_TOTALS[r.id]);
      return <TotalCell key={u} value={value} fromFallback={fromFallback} saving={saving} />;
    }
    return (
      <InputCell key={u} unit={u} field={r.key} value={rowOf(u)[r.key] ?? null} editable={cellEditable(u, r.key)}
        saving={saving} onChange={setCell} onLeave={onLeave} />
    );
  };

  const sumAcrossUnits = (r: PlanSectionRow) =>
    fmtNum(sumOrNull(units.map((u) => sectionRowValue(rowOf(u), r))), DIGITS);

  return (
    <div className={`card yp-grid-wrap${showTotal ? " table-scroll" : ""}`}>
      <table className="yp-grid">
        <thead>
          <tr>
            <th className="yp-label">Chỉ tiêu</th>
            {showTotal && <th className="yp-unit yp-sum">Tổng cộng</th>}
            {units.map((u) => (
              <th key={u} className="yp-unit">
                <div>{u}</div>
                {unitHeadExtra && <div className="yp-unit-extra">{unitHeadExtra(u)}</div>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {PLAN_SECTIONS.map((s) => (
            <Fragment key={s.title}>
              <tr className="yp-sec">
                <td className="yp-label">
                  <div className="yp-lab">
                    <span className="yp-name">{s.title}</span>
                    {SECTION_HINT[s.title] && <YearPlanHelpTip text={SECTION_HINT[s.title]} />}
                  </div>
                </td>
                {showTotal && <td className="yp-sum" />}
                <td colSpan={units.length} />
              </tr>
              {s.rows.map((r) => (
                <tr key={sectionRowId(r)} className={r.kind === "total" ? "yp-total" : undefined}>
                  <td className="yp-label"><RowLabel row={r} /></td>
                  {showTotal && <td className="yp-sum">{sumAcrossUnits(r)}</td>}
                  {units.map((u) => unitCell(u, r))}
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
