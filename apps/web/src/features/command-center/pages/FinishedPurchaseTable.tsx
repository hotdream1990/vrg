/* Bảng THU MUA THÀNH PHẨM của biểu Thu mua — mỗi dòng 1 CHỦNG LOẠI (chủng loại · SL · đơn giá ·
   loại tiền · tỷ giá → thành tiền tự tính). Cùng khuôn với bảng tiêu thụ/tồn kho ở ConsumptionForm. */

import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Select } from "antd";

import { FX_USD_VND, TONNES_DAILY, fxWarning, priceBound } from "../../../lib/entry-bounds";
import { CCYS, GRADES, type Ccy, priceUnitOf } from "../../../lib/unit-daily-consumption";
import { type FinishedLine, emptyFinishedLine, finishedLineVnd } from "../../../lib/unit-daily-purchase";
import { fmtNum } from "../../../lib/unit-daily-fields";
import { numInput } from "./unit-daily-inputs";

type Props = {
  rows: FinishedLine[];
  setRows: (next: FinishedLine[]) => void;
  readOnly?: boolean;
};

const num = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);
const cell = { width: "100%" } as const;

export default function FinishedPurchaseTable({ rows, setRows, readOnly }: Props) {
  const patch = (i: number, p: Partial<FinishedLine>) =>
    setRows(rows.map((l, j) => (j === i ? { ...l, ...p } : l)));
  const cols = readOnly ? 6 : 7;

  return (
    <>
      <div style={{ overflowX: "auto" }}>
        <table className="ud-sales ud-finished">
          <thead><tr style={{ fontSize: 11.5, textAlign: "left", opacity: 0.7 }}>
            <th style={{ width: "26%" }}>Chủng loại</th>
            <th style={{ width: "13%" }} className="r">SL thu mua (tấn)</th>
            <th style={{ width: "14%" }} className="r">Đơn giá</th>
            <th style={{ width: "11%" }}>Tiền</th>
            <th style={{ width: "13%" }} className="r">Tỷ giá</th>
            <th style={{ width: "17%" }} className="r">Thành tiền (triệu đ)</th>
            {!readOnly && <th style={{ width: "6%" }} />}
          </tr></thead>
          <tbody>
            {rows.map((ln, i) => (
              <tr key={i}>
                <td>
                  <Select size="small" style={cell} value={ln.grade || undefined} placeholder="Chủng loại"
                    disabled={readOnly} showSearch onChange={(v) => patch(i, { grade: v })}
                    options={GRADES.map((g) => ({ value: g, label: g }))} />
                </td>
                <td>{numInput(num(ln.qty), (v) => patch(i, { qty: v }), readOnly, "small", TONNES_DAILY)}</td>
                {/* Đơn giá đổi đơn vị theo loại tiền của DÒNG → nhãn phải nằm ở ô, không nằm ở <th>. */}
                <td>
                  {numInput(num(ln.price), (v) => patch(i, { price: v }), readOnly, "small", priceBound(ln.ccy))}
                  <div className="ud-unit-hint">{priceUnitOf(ln.ccy ?? "VND")}</div>
                </td>
                <td>
                  <Select size="small" style={cell} value={ln.ccy ?? "VND"} disabled={readOnly}
                    onChange={(v: Ccy) => patch(i, { ccy: v })} options={CCYS} />
                </td>
                <td>
                  {(ln.ccy ?? "VND") !== "VND"
                    ? numInput(num(ln.fx), (v) => patch(i, { fx: v }), readOnly, "small", FX_USD_VND, fxWarning(ln))
                    : <span style={{ fontSize: 11.5, color: "var(--muted)" }}>—</span>}
                </td>
                <td className="r" style={{ paddingRight: 6, fontWeight: 600, whiteSpace: "nowrap" }}>
                  {(() => { const v = finishedLineVnd(ln); return fmtNum(v == null ? null : v / 1_000_000, 1); })()}
                </td>
                {!readOnly && (
                  <td className="r">
                    <button type="button" className="btn" style={{ padding: "0 7px" }} title="Xoá dòng"
                      onClick={() => setRows(rows.filter((_, j) => j !== i))}><DeleteOutlined /></button>
                  </td>
                )}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={cols} style={{ textAlign: "center", color: "var(--muted)", padding: 12, fontSize: 12.5 }}>
                Chưa có chủng loại nào — ngày nào không mua thành phẩm thì để trống.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      {!readOnly && (
        <button type="button" className="btn" style={{ marginTop: 8, fontSize: 12 }}
          onClick={() => setRows([...rows, emptyFinishedLine()])}><PlusOutlined /> Thêm chủng loại</button>
      )}
    </>
  );
}
