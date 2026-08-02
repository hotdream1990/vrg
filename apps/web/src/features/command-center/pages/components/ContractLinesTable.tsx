import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";

import type { ContractLine, ContractMeta } from "../../../../lib/sales-contract-client";
import NumInput from "../../sections/NumInput";

export const EMPTY_LINE: ContractLine = {
  grade: "", qty: null, qty_dry: null, price: null, ccy: "VND", fx: null, cost: null,
};

type Props = {
  lines: ContractLine[];
  meta: ContractMeta;
  /** true khi dòng thuộc MỘT LẦN GIAO thật (phụ lục / HĐ giao-1-lần đã giao) → ép quy khô. */
  requireDry: boolean;
  /** Loại tiền được phép của ĐƠN VỊ đang chọn (đã lọc ở form) — không dùng thẳng meta.currencies. */
  currencies: string[];
  readOnly?: boolean;
  onChange: (lines: ContractLine[]) => void;
};

/** Ô số của bảng — dùng NumInput chung để gõ được thập phân (giữ chuỗi thô khi đang gõ). */
const cell = (value: number | null, onChange: (v: number | null) => void,
              readOnly?: boolean, warn = false, placeholder = "") => (
  <NumInput value={value} onChange={onChange} readOnly={readOnly} placeholder={placeholder}
            className={`blt-date-input r${warn ? " num-warn" : ""}`} />
);

/** Bảng dòng chi tiết hợp đồng: chủng loại · tấn · quy khô · đơn giá · loại tiền · tỷ giá · chi phí. */
export default function ContractLinesTable({ lines, meta, requireDry, currencies, readOnly, onChange }: Props) {
  const dry = new Set(meta.dry_required);
  const set = (i: number, patch: Partial<ContractLine>) =>
    onChange(lines.map((ln, k) => (k === i ? { ...ln, ...patch } : ln)));
  // Bán bằng VNĐ thì không có gì để quy đổi → cả bảng VNĐ là BỎ HẲN cột tỷ giá, đỡ một cột trống
  // khiến người nhập tưởng còn thiếu số. Bảng có dòng ngoại tệ thì giữ cột, dòng VNĐ để dấu "—".
  const anyFx = lines.some((ln) => ln.ccy !== "VND");
  // Cột quy khô cũng vậy: cả bảng toàn thành phẩm thì bỏ hẳn cột. Bảng có latex/mủ nguyên liệu thì
  // giữ cột (một hợp đồng bán nhiều chủng loại), dòng thành phẩm để dấu "—".
  const anyDry = lines.some((ln) => dry.has(ln.grade));

  return (
    <div>
      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table>
          <thead><tr>
            <th style={{ minWidth: 220 }}>Chủng loại</th>
            <th className="r">SL (tấn)</th>
            {anyDry && <th className="r">Quy khô (tấn)</th>}
            <th className="r">Đơn giá<div style={{ fontWeight: 400, opacity: .7, fontSize: 11 }}>tr.đ/tấn · ngoại tệ/tấn</div></th>
            <th>Loại tiền</th>
            {anyFx && <th className="r">Tỷ giá → VNĐ</th>}
            <th className="r">Chi phí (tr.đ)<div style={{ fontWeight: 400, opacity: .7, fontSize: 11 }}>chi phí lô hàng</div></th>
            {!readOnly && <th style={{ width: 44 }} />}
          </tr></thead>
          <tbody>
            {lines.map((ln, i) => {
              const needDry = requireDry && dry.has(ln.grade);
              const needFx = ln.ccy !== "VND";
              return (
                <tr key={i}>
                  <td>
                    <select className="blt-date-input" style={{ width: "100%" }} value={ln.grade}
                      disabled={readOnly}
                      // Đổi sang chủng loại không có quy khô phải XOÁ số cũ: ô đã ẩn nên người dùng
                      // không tự xoá được, giữ lại thì lưu bị chặn mà không biết sửa ở đâu.
                      onChange={(e) => set(i, {
                        grade: e.target.value,
                        ...(dry.has(e.target.value) ? {} : { qty_dry: null }),
                      })}>
                      <option value="">— chọn chủng loại —</option>
                      {meta.grades.map((g) => <option key={g} value={g}>{g}</option>)}
                    </select>
                  </td>
                  <td className="r">{cell(ln.qty, (v) => set(i, { qty: v }), readOnly)}</td>
                  {anyDry && (
                    <td className="r">
                      {/* Thành phẩm bán ra đã là hàng khô → không có quy khô, tránh khai số vô nghĩa. */}
                      {dry.has(ln.grade)
                        ? cell(ln.qty_dry, (v) => set(i, { qty_dry: v }), readOnly,
                               needDry && !ln.qty_dry, needDry ? "bắt buộc" : "")
                        : <span style={{ fontSize: 11.5, color: "var(--muted)" }}>—</span>}
                    </td>
                  )}
                  <td className="r">
                    {cell(ln.price, (v) => set(i, { price: v }), readOnly)}
                    <div className="ud-unit-hint">{ln.ccy === "VND" ? "tr.đ/tấn" : `${ln.ccy}/tấn`}</div>
                  </td>
                  <td>
                    <select className="blt-date-input" style={{ width: 84 }} value={ln.ccy}
                      disabled={readOnly} onChange={(e) => set(i, { ccy: e.target.value })}>
                      {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </td>
                  {anyFx && (
                    <td className="r">
                      {needFx
                        ? cell(ln.fx, (v) => set(i, { fx: v }), readOnly, !ln.fx, "bắt buộc")
                        : <span style={{ fontSize: 11.5, color: "var(--muted)" }}>—</span>}
                    </td>
                  )}
                  <td className="r">{cell(ln.cost, (v) => set(i, { cost: v }), readOnly)}</td>
                  {!readOnly && (
                    <td className="r">
                      <button className="btn" title="Xoá dòng" disabled={lines.length <= 1}
                        onClick={() => onChange(lines.filter((_, k) => k !== i))}>
                        <DeleteOutlined />
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!readOnly && (
        <div style={{ marginTop: 8 }}>
          <button className="btn" onClick={() => onChange([...lines, { ...EMPTY_LINE }])}>
            <PlusOutlined /> Thêm dòng
          </button>
        </div>
      )}
      <div className="form-note" style={{ fontSize: 11.5, marginTop: 6 }}>
        Đơn giá: bán bằng <b>VNĐ</b> nhập theo <b>triệu đồng/tấn</b>; bán bằng ngoại tệ nhập theo
        <b> ngoại tệ/tấn</b> và phải có tỷ giá quy ra VNĐ. Bán <b>LATEX</b> và 2 loại mủ nguyên liệu
        mới thì <b>bắt buộc nhập quy khô</b> mới lưu được.
      </div>
    </div>
  );
}
