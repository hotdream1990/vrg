import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";

import { TONNES_CONTRACT, boundWarning } from "../../../../lib/entry-bounds";
import type { MasterLine } from "../../../../lib/master-contract-client";
import NumInput from "../../sections/NumInput";

export const EMPTY_MASTER_LINE: MasterLine = { grade: "", qty: null, qty_dry: null };

type Props = {
  lines: MasterLine[];
  grades: string[];
  /** Chủng loại bán theo MỦ NƯỚC → phải khai thêm quy khô (`meta.dry_required`). */
  dryGrades: string[];
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
 * Dòng CAM KẾT của hợp đồng mẹ: chủng loại · số lượng · quy khô (latex và mủ nguyên liệu).
 *
 * KHÔNG có đơn giá / loại tiền / tỷ giá (chốt 25/08/2026): hồ sơ mẹ cam kết CHỦNG LOẠI và SẢN
 * LƯỢNG, còn giá là số của từng chuyến — khai ở phụ lục, hoặc đi theo CÔNG THỨC GIÁ của hồ sơ.
 *
 * KHÁC dòng hợp đồng bán (`ContractLinesTable`): số lượng ĐỂ TRỐNG được, vì HĐ nguyên tắc thường
 * chỉ chốt chủng loại. Đã cam kết số lượng thì quy khô mới bắt buộc.
 */
export default function MasterLinesTable({ lines, grades, dryGrades, readOnly, onChange }: Props) {
  const dry = new Set(dryGrades);
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
          const hasDry = dry.has(ln.grade);
          const qtyWarn = boundWarning(ln.qty, TONNES_CONTRACT);
          // Chỉ nhắc quy khô khi ĐÃ cam kết số lượng — chưa có số lượng thì để trống là bình thường.
          const dryWarn = hasDry && ln.qty != null && !ln.qty_dry
            ? "Đã cam kết số lượng thì phải nhập quy khô."
            : (ln.qty != null && ln.qty_dry != null && ln.qty_dry > ln.qty
              ? "Quy khô không thể lớn hơn số lượng." : null);
          return (
            <div className="ct-line" key={i}>
              <Field label="Chủng loại *" w={230}>
                <select className="blt-date-input" value={ln.grade} disabled={readOnly}
                  // Đổi sang chủng loại không có quy khô phải XOÁ số cũ: ô đã ẩn nên người dùng
                  // không tự xoá được, giữ lại thì lưu bị chặn mà không biết sửa ở đâu.
                  onChange={(e) => set(i, {
                    grade: e.target.value,
                    ...(dry.has(e.target.value) ? {} : { qty_dry: null }),
                  })}>
                  <option value="">— chọn chủng loại —</option>
                  {grades.map((g) => <option key={g} value={g}>{g}</option>)}
                </select>
              </Field>
              {/* Chủng loại còn nước cam kết theo SỐ CHƯA QUY KHÔ — ghi thẳng vào nhãn, giống
                  phiếu hợp đồng, để không ai hiểu nhầm đây là sản lượng khô. */}
              <Field label={hasDry ? "SL chưa quy khô (tấn)" : "SL (tấn)"} w={150}>
                {num(ln.qty, (v) => set(i, { qty: v }), qtyWarn)}
              </Field>
              {hasDry && (
                <Field label="Quy khô (tấn)" w={130}>
                  {num(ln.qty_dry, (v) => set(i, { qty_dry: v }), dryWarn)}
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
        Mỗi chủng loại một dòng. <b>Số lượng để trống được</b> nếu hợp đồng chưa chốt sản lượng —
        số thật của từng chuyến khai ở phụ lục. Hồ sơ mẹ <b>không nhập đơn giá</b>: giá theo từng
        chuyến ở phụ lục, hoặc ghi ở ô <b>Công thức giá</b> (HĐ dài hạn). Cam kết <b>LATEX</b> và 2
        loại mủ nguyên liệu, <b>mủ dây</b> thì <b>SL chưa quy khô</b> phải đi kèm <b>quy khô</b>.
      </div>
    </div>
  );
}
