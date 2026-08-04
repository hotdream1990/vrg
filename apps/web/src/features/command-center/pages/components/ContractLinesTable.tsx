import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";

import type { ContractLine, ContractMeta } from "../../../../lib/sales-contract-client";
import NumInput from "../../sections/NumInput";

const fmtAmount = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });

export const EMPTY_LINE: ContractLine = {
  grade: "", qty: null, qty_dry: null, price: null, ccy: "VND", fx: null,
};

/** Thành tiền của 1 dòng theo NGUYÊN TỆ của dòng (VNĐ: triệu đồng · ngoại tệ: chính nó).
 *  Không quy đổi ở mức dòng vì đơn giá vốn nhập theo nguyên tệ — quy đổi để dành cho ô tổng. */
export const lineAmount = (ln: ContractLine): number | null =>
  (ln.qty == null || ln.price == null ? null : ln.qty * ln.price);

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

/** Một ô có nhãn trong dòng chi tiết. `w` = bề rộng mong muốn, ô vẫn co lại được khi khung hẹp. */
function Field({ label, w, children }: { label: string; w: number; children: React.ReactNode }) {
  return (
    <label className="form-field" style={{ flex: `0 1 ${w}px`, minWidth: 84 }}>
      <span>{label}</span>
      {children}
    </label>
  );
}

/**
 * Dòng chi tiết hợp đồng: chủng loại · sản lượng · quy khô · đơn giá · loại tiền · tỷ giá ·
 * THÀNH TIỀN (tự tính, chỉ đọc).
 *
 * Bố cục là KHỐI TỰ XUỐNG HÀNG, không phải bảng: nhiều cột luôn vượt bề ngang modal nên người nhập
 * phải cuộn ngang mới thấy ô cuối. Mỗi ô mang nhãn riêng nên xuống hàng vẫn đọc được, và ô nào không
 * áp dụng cho dòng đó thì ẩn hẳn thay vì để một ô trống khiến người nhập tưởng còn thiếu số:
 *   - Quy khô: chỉ latex và mủ nguyên liệu (thành phẩm bán ra vốn đã là hàng khô).
 *   - Tỷ giá: chỉ dòng bán bằng ngoại tệ.
 */
export default function ContractLinesTable({ lines, meta, requireDry, currencies, readOnly, onChange }: Props) {
  const dry = new Set(meta.dry_required);
  const set = (i: number, patch: Partial<ContractLine>) =>
    onChange(lines.map((ln, k) => (k === i ? { ...ln, ...patch } : ln)));

  const num = (value: number | null, onValue: (v: number | null) => void,
               warn = false, placeholder = "") => (
    <NumInput value={value} onChange={onValue} readOnly={readOnly} placeholder={placeholder}
              className={`blt-date-input r${warn ? " num-warn" : ""}`} />
  );
  const amount = (i: number) => lineAmount(lines[i]);

  return (
    <div>
      <div className="card" style={{ padding: "0 12px" }}>
        {lines.map((ln, i) => {
          const hasDry = dry.has(ln.grade);
          const needDry = requireDry && hasDry;
          const needFx = ln.ccy !== "VND";
          return (
            <div className="ct-line" key={i}>
              <Field label="Chủng loại" w={230}>
                <select className="blt-date-input" value={ln.grade} disabled={readOnly}
                  // Đổi sang chủng loại không có quy khô phải XOÁ số cũ: ô đã ẩn nên người dùng
                  // không tự xoá được, giữ lại thì lưu bị chặn mà không biết sửa ở đâu.
                  onChange={(e) => set(i, {
                    grade: e.target.value,
                    ...(dry.has(e.target.value) ? {} : { qty_dry: null }),
                  })}>
                  <option value="">— chọn chủng loại —</option>
                  {meta.grades.map((g) => <option key={g} value={g}>{g}</option>)}
                </select>
              </Field>
              {/* Latex + 2 loại mủ nguyên liệu bán theo MỦ NƯỚC — ghi thẳng vào nhãn, vì tiền
                  tính trên số này còn sản lượng tiêu thụ trên báo cáo lại lấy ô Quy khô. */}
              <Field label={hasDry ? "SL nước (tấn)" : "SL (tấn)"} w={110}>
                {num(ln.qty, (v) => set(i, { qty: v }))}
              </Field>
              {hasDry && (
                <Field label="Quy khô (tấn)" w={110}>
                  {num(ln.qty_dry, (v) => set(i, { qty_dry: v }), needDry && !ln.qty_dry,
                       needDry ? "bắt buộc" : "")}
                </Field>
              )}
              <Field label={`Đơn giá (${ln.ccy === "VND" ? "tr.đ/tấn" : `${ln.ccy}/tấn`})`} w={130}>
                {num(ln.price, (v) => set(i, { price: v }))}
              </Field>
              <Field label="Loại tiền" w={92}>
                <select className="blt-date-input" value={ln.ccy} disabled={readOnly}
                  onChange={(e) => set(i, { ccy: e.target.value })}>
                  {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </Field>
              {needFx && (
                <Field label="Tỷ giá → VNĐ" w={120}>
                  {num(ln.fx, (v) => set(i, { fx: v }), !ln.fx, "bắt buộc")}
                </Field>
              )}
              {/* Thành tiền = SL × đơn giá, hiện theo ĐÚNG loại tiền của dòng. Ô CHỈ ĐỌC — sửa
                  được thì người nhập sẽ sửa tay rồi lệch với số hệ thống tính cho báo cáo. */}
              <Field label={`Thành tiền (${ln.ccy === "VND" ? "tr.đ" : ln.ccy})`} w={140}>
                <input className="blt-date-input r" readOnly tabIndex={-1}
                  style={{ background: "transparent", fontWeight: 500 }}
                  value={amount(i) == null ? "—" : fmtAmount(amount(i) as number)} />
              </Field>
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
          <button className="btn" onClick={() => onChange([...lines, { ...EMPTY_LINE }])}>
            <PlusOutlined /> Thêm dòng
          </button>
        </div>
      )}
      <div className="form-note" style={{ fontSize: 11.5, marginTop: 6 }}>
        Đơn giá: bán bằng <b>VNĐ</b> nhập theo <b>triệu đồng/tấn</b>; bán bằng ngoại tệ nhập theo
        <b> ngoại tệ/tấn</b> và phải có tỷ giá quy ra VNĐ. Bán <b>LATEX</b> và 2 loại mủ nguyên liệu
        mới thì <b>bắt buộc nhập quy khô</b> mới lưu được.
        <br />
        Với 3 chủng loại đó: <b>SL nước</b> là số để tính <b>thành tiền</b> (đơn giá là giá theo tấn
        mủ nước), còn <b>sản lượng tiêu thụ trên báo cáo lấy theo số quy khô</b>.
      </div>
    </div>
  );
}
