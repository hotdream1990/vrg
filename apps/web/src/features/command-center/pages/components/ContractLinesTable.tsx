import { DeleteOutlined, PlusOutlined, WarningOutlined } from "@ant-design/icons";

import {
  FX_USD_VND, TONNES_CONTRACT, boundWarning, fxWarning, priceBound,
} from "../../../../lib/entry-bounds";
import type { ContractLine, ContractMeta } from "../../../../lib/sales-contract-client";
import DateInput from "../../sections/DateInput";
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
  /** Loại tiền được phép của ĐƠN VỊ đang chọn (đã lọc ở form) — không dùng thẳng meta.currencies. */
  currencies: string[];
  /** Bản ghi ĐÃ CÓ NGÀY GIAO → tỷ giá là bắt buộc. Chưa giao thì chưa ai biết tỷ giá ngày giao,
   *  ép nhập chỉ tổ bắt đơn vị bịa số (chốt 22/08/2026) — phải khớp `require_fx` ở server. */
  requireFx?: boolean;
  /** Có truyền (kể cả null) = hiện ô "Hiệu lực từ" từng dòng, chặn chọn trước ngày ký này. Chỉ
   *  truyền khi SỬA hợp đồng — lúc tạo mọi dòng đều theo ngày ký, form giữ tối giản. */
  signDate?: string | null;
  /** Hạn trên của "Hiệu lực từ": ngày giao của hợp đồng giao 1 lần (giao rồi thì không tăng thêm). */
  maxFromDate?: string | null;
  readOnly?: boolean;
  onChange: (lines: ContractLine[]) => void;
};

/** Cảnh báo NHẦM ĐƠN VỊ TÍNH của một dòng — chìa khoá là ô đơn giá.
 *
 *  Vì sao phải có ở đây: rà production ngày 10/08/2026 thấy 47 dòng nhập đơn giá theo ĐỒNG/tấn
 *  (61.600.000) hoặc NGHÌN ĐỒNG/tấn (49.850) trong khi ô tính bằng TRIỆU ĐỒNG/tấn → doanh thu
 *  tiêu thụ bị thổi tới 8.748.352 tỷ đồng (số đúng ~1.065 tỷ). Bộ biên `entry-bounds` được dựng
 *  đúng cho lỗi này từ 07/2026 nhưng chỉ gắn ở biểu nhập ngày; khi tiêu thụ chuyển sang nhập ở
 *  hợp đồng (30/07/2026) thì màn mới KHÔNG có cảnh báo nào — lỗi cũ lặp lại y nguyên.
 *  CHỈ CẢNH BÁO, không chặn lưu: giá thị trường có thể vượt biên thật, chặn cứng là chặn nghiệp vụ.
 */
function lineWarnings(ln: ContractLine, needDry: boolean, requireFx: boolean) {
  return {
    qty: boundWarning(ln.qty, TONNES_CONTRACT),
    qty_dry: needDry && !ln.qty_dry ? "Bắt buộc nhập quy khô mới lưu được." : null,
    price: boundWarning(ln.price, priceBound(ln.ccy)),
    // Chưa có ngày giao thì tỷ giá trống là BÌNH THƯỜNG, không phải ô cần kiểm tra — nhắc ở đây
    // sẽ hiện cảnh báo trên gần như mọi hợp đồng ngoại tệ mới ký.
    fx: (requireFx ? fxWarning(ln) : null) ?? boundWarning(ln.fx, FX_USD_VND),
  };
}

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
 *   - Hiệu lực từ: chỉ khi SỬA hợp đồng (`signDate`), không bao giờ ở đợt giao.
 */
export default function ContractLinesTable({
  lines, meta, currencies, requireFx = false, signDate, maxFromDate, readOnly, onChange,
}: Props) {
  const dry = new Set(meta.dry_required);
  const dated = signDate !== undefined;
  const set = (i: number, patch: Partial<ContractLine>) =>
    onChange(lines.map((ln, k) => (k === i ? { ...ln, ...patch } : ln)));

  /** Ô số + viền cảnh báo. `warn` = lời nhắc (null = bình thường) → rê chuột lên ô thấy đơn vị tính.
   *
   *  KHÔNG bọc/gỡ <Tooltip> theo `warn`: đổi kiểu phần tử gốc giữa lúc gõ làm React remount thẻ
   *  input → vừa gõ ký tự đầu (đơn giá "1" đã dưới biên 10 triệu đ/tấn) là cảnh báo bật, con trỏ
   *  văng khỏi ô và chuỗi đang gõ dở bị nắn lại. Lời nhắc đi bằng `title` để cây phần tử giữ
   *  NGUYÊN ở cả hai trạng thái — đúng cách `NumInput` đã xử lý cho icon cảnh báo bên trong nó. */
  const num = (value: number | null, onValue: (v: number | null) => void,
               warn: string | null = null, placeholder = "") => (
    <NumInput value={value} onChange={onValue} readOnly={readOnly} placeholder={placeholder}
              title={warn ?? undefined}
              className={`blt-date-input r${warn ? " num-warn" : ""}`} />
  );
  const amount = (i: number) => lineAmount(lines[i]);
  // Gom cảnh báo của MỌI dòng: ô lệch rất dễ nằm ngoài tầm nhìn khi khối tự xuống hàng, chỉ tô
  // viền thôi thì người nhập vẫn bấm Lưu mà không thấy gì (bài học của banner biểu nhập ngày).
  const alerts = lines.flatMap((ln, i) => {
    const w = lineWarnings(ln, dry.has(ln.grade), requireFx);
    return ([["Sản lượng", w.qty], ["Quy khô", w.qty_dry], ["Đơn giá", w.price],
             ["Tỷ giá", w.fx]] as const)
      .filter(([, m]) => m)
      .map(([field, m]) => `Dòng ${i + 1} · ${field}: ${m}`);
  });

  return (
    <div>
      <div className="card" style={{ padding: "0 12px" }}>
        {lines.map((ln, i) => {
          const hasDry = dry.has(ln.grade);
          const needFx = ln.ccy !== "VND";
          const w = lineWarnings(ln, hasDry, requireFx);
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
              {/* Chủng loại còn nước (latex · mủ nguyên liệu · mủ dây) bán theo SỐ CHƯA QUY KHÔ —
                  ghi thẳng vào nhãn, vì tiền tính trên số này còn sản lượng tiêu thụ trên báo cáo
                  lại lấy ô Quy khô. */}
              <Field label={hasDry ? "SL chưa quy khô (tấn)" : "SL (tấn)"} w={140}>
                {num(ln.qty, (v) => set(i, { qty: v }), w.qty)}
              </Field>
              {hasDry && (
                <Field label="Quy khô (tấn) *" w={110}>
                  {num(ln.qty_dry, (v) => set(i, { qty_dry: v }), w.qty_dry, "bắt buộc")}
                </Field>
              )}
              <Field label={`Đơn giá (${ln.ccy === "VND" ? "tr.đ/tấn" : `${ln.ccy}/tấn`})`} w={130}>
                {num(ln.price, (v) => set(i, { price: v }), w.price)}
              </Field>
              <Field label="Loại tiền" w={92}>
                <select className="blt-date-input" value={ln.ccy} disabled={readOnly}
                  onChange={(e) => set(i, { ccy: e.target.value })}>
                  {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </Field>
              {needFx && (
                <Field label={`Tỷ giá → VNĐ${requireFx ? " *" : ""}`} w={120}>
                  {/* Chưa có ngày giao thì để trống được — ghi rõ "khi giao" thay vì "bắt buộc",
                      không thì người nhập tưởng đang thiếu số mà không sao lưu nổi. */}
                  {num(ln.fx, (v) => set(i, { fx: v }), w.fx, requireFx ? "bắt buộc" : "khi giao")}
                </Field>
              )}
              {/* Thành tiền = SL × đơn giá, hiện theo ĐÚNG loại tiền của dòng. Ô CHỈ ĐỌC — sửa
                  được thì người nhập sẽ sửa tay rồi lệch với số hệ thống tính cho báo cáo. */}
              <Field label={`Thành tiền (${ln.ccy === "VND" ? "tr.đ" : ln.ccy})`} w={140}>
                <input className="blt-date-input r" readOnly tabIndex={-1}
                  style={{ background: "transparent", fontWeight: 500 }}
                  value={amount(i) == null ? "—" : fmtAmount(amount(i) as number)} />
              </Field>
              {dated && (
                <Field label="Hiệu lực từ" w={140}>
                  <DateInput value={ln.from_date ?? ""} readOnly={readOnly} allowClear
                    minDate={signDate ?? undefined} maxDate={maxFromDate ?? undefined}
                    placeholder="theo ngày ký" style={{ width: "100%" }}
                    onChange={(v) => set(i, { from_date: v || null })} />
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
          <button className="btn" onClick={() => onChange([...lines, { ...EMPTY_LINE }])}>
            <PlusOutlined /> Thêm dòng
          </button>
        </div>
      )}
      {alerts.length > 0 && (
        <div className="blt-error" style={{ marginTop: 8, fontSize: 12.5 }}>
          <b><WarningOutlined /> {alerts.length} ô cần kiểm tra lại</b>
          <ul style={{ margin: "4px 0 0", paddingLeft: 20 }}>
            {alerts.map((a) => <li key={a}>{a}</li>)}
          </ul>
        </div>
      )}
      <div className="form-note" style={{ fontSize: 11.5, marginTop: 6 }}>
        Đơn giá: bán bằng <b>VNĐ</b> nhập theo <b>triệu đồng/tấn</b>; bán bằng ngoại tệ nhập theo
        <b> ngoại tệ/tấn</b>. <b>Tỷ giá</b> chỉ bắt buộc khi đã điền <b>Ngày giao</b> — lúc ký hợp
        đồng chưa biết tỷ giá ngày giao hàng, để trống thì doanh thu tạm để trống chứ không tính
        bằng 0. Bán <b>LATEX</b>, 2 loại mủ nguyên liệu và <b>mủ dây</b> thì{" "}
        <b>bắt buộc nhập quy khô</b> mới lưu được — cả lúc tạo lẫn lúc sửa, kể cả hợp đồng chưa giao.
        <br />
        Với các chủng loại đó: <b>SL chưa quy khô</b> là số để tính <b>thành tiền</b> (đơn giá là giá
        theo tấn hàng chưa quy khô), còn{" "}
        <b>sản lượng tiêu thụ trên báo cáo lấy theo số quy khô</b>.
        {/* Tăng = dòng MỚI có ngày hiệu lực, không sửa số dòng cũ: sửa số dòng cũ là đổi luôn số
            "đã ký chưa giao" của mọi ngày trước ngày điều chỉnh (chốt 30/09/2026). */}
        {dated && (
          <>
            <br />
            <b>Tăng sản lượng sau khi ký</b>: bấm <b>Thêm dòng</b>, chọn chủng loại, nhập{" "}
            <b>phần tăng thêm</b> và điền <b>Hiệu lực từ</b> = ngày điều chỉnh — từ ngày đó phần tăng
            mới tính vào “đã ký HĐ chưa giao”. Để trống = tính từ ngày ký.{" "}
            <b>Giảm sản lượng</b>: sửa thẳng số lượng của dòng.
          </>
        )}
      </div>
    </div>
  );
}
