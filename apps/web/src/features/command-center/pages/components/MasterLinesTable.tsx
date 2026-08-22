import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";

import { FX_USD_VND, boundWarning, fxWarning, priceBound } from "../../../../lib/entry-bounds";
import type { MasterLine } from "../../../../lib/master-contract-client";
import NumInput from "../../sections/NumInput";

export const EMPTY_MASTER_LINE: MasterLine = {
  grade: "", qty: null, price: null, ccy: "VND", fx: null,
};

type Props = {
  lines: MasterLine[];
  grades: string[];
  /** Loại tiền được phép của ĐƠN VỊ đang chọn (đã lọc ở form) — không hiện cả LAK lẫn KHR. */
  currencies: string[];
  readOnly?: boolean;
  onChange: (lines: MasterLine[]) => void;
};

function Field({ label, w, children }: { label: string; w: number; children: React.ReactNode }) {
  return (
    <label className="form-field" style={{ flex: `0 1 ${w}px`, minWidth: 96 }}>
      <span>{label}</span>
      {children}
    </label>
  );
}

/**
 * Dòng CAM KẾT của hợp đồng mẹ: chủng loại · số lượng · ĐƠN GIÁ riêng cho chủng loại đó · loại
 * tiền · tỷ giá. Một hợp đồng mẹ có nhiều chủng loại, mỗi chủng loại một đơn giá.
 *
 * KHÁC dòng hợp đồng bán (`ContractLinesTable`):
 *   - KHÔNG có ô quy khô: quy khô là dữ kiện của lần bán thật, khai ở phụ lục / đợt giao.
 *   - Số lượng và đơn giá ĐỂ TRỐNG được: HĐ nguyên tắc thường chỉ chốt chủng loại, giá đi theo
 *     công thức hoặc thoả thuận từng chuyến. Vẫn cảnh báo biên khi đã nhập, để không lọt lỗi
 *     nhầm đơn vị tính (đơn giá gõ theo đồng/tấn thay vì triệu đồng/tấn).
 */
export default function MasterLinesTable({ lines, grades, currencies, readOnly, onChange }: Props) {
  const set = (i: number, patch: Partial<MasterLine>) =>
    onChange(lines.map((ln, k) => (k === i ? { ...ln, ...patch } : ln)));

  const num = (value: number | null, onValue: (v: number | null) => void,
               warn: string | null = null, placeholder = "") => (
    <NumInput value={value} onChange={onValue} readOnly={readOnly} placeholder={placeholder}
              title={warn ?? undefined}
              className={`blt-date-input r${warn ? " num-warn" : ""}`} />
  );

  return (
    <div>
      <div className="card" style={{ padding: "0 12px" }}>
        {lines.map((ln, i) => {
          const needFx = ln.ccy !== "VND" && ln.price != null;
          const priceWarn = boundWarning(ln.price, priceBound(ln.ccy, ln.grade));
          const fxWarn = fxWarning(ln) ?? boundWarning(ln.fx, FX_USD_VND);
          return (
            <div className="ct-line" key={i}>
              <Field label="Chủng loại *" w={230}>
                <select className="blt-date-input" value={ln.grade} disabled={readOnly}
                  onChange={(e) => set(i, { grade: e.target.value })}>
                  <option value="">— chọn chủng loại —</option>
                  {grades.map((g) => <option key={g} value={g}>{g}</option>)}
                </select>
              </Field>
              <Field label="Số lượng (tấn)" w={130}>
                {num(ln.qty, (v) => set(i, { qty: v }), null, "chưa cam kết")}
              </Field>
              <Field label={`Đơn giá (${ln.ccy === "VND" ? "tr.đ/tấn" : `${ln.ccy}/tấn`})`} w={140}>
                {num(ln.price, (v) => set(i, { price: v }), priceWarn, "chưa chốt")}
              </Field>
              <Field label="Loại tiền" w={96}>
                <select className="blt-date-input" value={ln.ccy} disabled={readOnly}
                  onChange={(e) => set(i, { ccy: e.target.value })}>
                  {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </Field>
              {needFx && (
                <Field label="Tỷ giá → VNĐ" w={130}>
                  {num(ln.fx, (v) => set(i, { fx: v }), fxWarn, "bắt buộc")}
                </Field>
              )}
              {!readOnly && (
                <button className="btn" title="Xoá dòng" disabled={lines.length <= 1}
                  style={{ marginBottom: 1 }}
                  onClick={() => onChange(lines.filter((_, k) => k !== i))}>
                  <DeleteOutlined />
                </button>
              )}
            </div>
          );
        })}
      </div>
      {!readOnly && (
        <div style={{ marginTop: 8 }}>
          <button className="btn" onClick={() => onChange([...lines, { ...EMPTY_MASTER_LINE }])}>
            <PlusOutlined /> Thêm chủng loại
          </button>
        </div>
      )}
      <div className="form-note" style={{ fontSize: 11.5, marginTop: 6 }}>
        Mỗi chủng loại một dòng, có <b>đơn giá riêng</b>. Đơn giá bán bằng <b>VNĐ</b> nhập theo{" "}
        <b>triệu đồng/tấn</b>; bằng ngoại tệ nhập theo <b>ngoại tệ/tấn</b> và phải có tỷ giá quy ra
        VNĐ. <b>Số lượng và đơn giá được để trống</b> nếu hợp đồng chưa chốt — số thật của từng
        chuyến khai ở phụ lục.
      </div>
    </div>
  );
}
