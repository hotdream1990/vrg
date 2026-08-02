import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";

import type { ContractLine, ContractMeta } from "../../../../lib/sales-contract-client";

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

const num = (s: string) => (s.trim() === "" ? null : Number(s.replace(/\s/g, "").replace(/,/g, ".")));
const str = (v: number | null) => (v == null ? "" : String(v));

/** Bảng dòng chi tiết hợp đồng: chủng loại · tấn · quy khô · đơn giá · loại tiền · tỷ giá · chi phí. */
export default function ContractLinesTable({ lines, meta, requireDry, currencies, readOnly, onChange }: Props) {
  const dry = new Set(meta.dry_required);
  const set = (i: number, patch: Partial<ContractLine>) =>
    onChange(lines.map((ln, k) => (k === i ? { ...ln, ...patch } : ln)));

  return (
    <div>
      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table>
          <thead><tr>
            <th style={{ minWidth: 220 }}>Chủng loại</th>
            <th className="r">SL (tấn)</th>
            <th className="r">Quy khô (tấn)</th>
            <th className="r">Đơn giá<div style={{ fontWeight: 400, opacity: .7, fontSize: 11 }}>tr.đ/tấn · ngoại tệ/tấn</div></th>
            <th>Loại tiền</th>
            <th className="r">Tỷ giá → VNĐ</th>
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
                      disabled={readOnly} onChange={(e) => set(i, { grade: e.target.value })}>
                      <option value="">— chọn chủng loại —</option>
                      {meta.grades.map((g) => <option key={g} value={g}>{g}</option>)}
                    </select>
                  </td>
                  <td className="r">
                    <input className="blt-date-input r" style={{ width: 92 }} inputMode="decimal"
                      disabled={readOnly} value={str(ln.qty)}
                      onChange={(e) => set(i, { qty: num(e.target.value) })} />
                  </td>
                  <td className="r">
                    <input className={`blt-date-input r${needDry && !ln.qty_dry ? " num-warn" : ""}`}
                      style={{ width: 92 }} inputMode="decimal" disabled={readOnly} value={str(ln.qty_dry)}
                      placeholder={needDry ? "bắt buộc" : ""}
                      onChange={(e) => set(i, { qty_dry: num(e.target.value) })} />
                  </td>
                  <td className="r">
                    <input className="blt-date-input r" style={{ width: 100 }} inputMode="decimal"
                      disabled={readOnly} value={str(ln.price)}
                      onChange={(e) => set(i, { price: num(e.target.value) })} />
                    <div className="ud-unit-hint">{ln.ccy === "VND" ? "tr.đ/tấn" : `${ln.ccy}/tấn`}</div>
                  </td>
                  <td>
                    <select className="blt-date-input" style={{ width: 84 }} value={ln.ccy}
                      disabled={readOnly} onChange={(e) => set(i, { ccy: e.target.value })}>
                      {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </td>
                  <td className="r">
                    <input className={`blt-date-input r${needFx && !ln.fx ? " num-warn" : ""}`}
                      style={{ width: 100 }} inputMode="decimal" disabled={readOnly || !needFx}
                      value={str(ln.fx)} placeholder={needFx ? "bắt buộc" : "—"}
                      onChange={(e) => set(i, { fx: num(e.target.value) })} />
                  </td>
                  <td className="r">
                    <input className="blt-date-input r" style={{ width: 92 }} inputMode="decimal"
                      disabled={readOnly} value={str(ln.cost)}
                      onChange={(e) => set(i, { cost: num(e.target.value) })} />
                  </td>
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
