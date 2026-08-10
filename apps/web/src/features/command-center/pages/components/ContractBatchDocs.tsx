import type { Contract, ContractDoc } from "../../../../lib/sales-contract-client";
import DateInput from "../../sections/DateInput";
import NumInput from "../../sections/NumInput";
import ContractAttach from "./ContractAttach";

type Props = {
  c: Contract;
  set: (patch: Partial<Contract>) => void;
};

const GRID: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))", gap: 10,
};

/** Hoá đơn + thanh toán của MỘT ĐỢT GIAO.
 *
 *  Dùng cho cả đợt giao lẫn hợp đồng giao-1-lần (hợp đồng đó chính là một đợt). Tách khỏi
 *  `ContractFormModal` để form nhập không phình quá một màn hình đọc. */
export default function ContractBatchDocs({ c, set }: Props) {
  return (
    <>
      <h4 style={{ margin: "14px 0 6px" }}>Hoá đơn</h4>
      <div style={GRID}>
        <label className="form-field">Số hoá đơn
          <input className="blt-date-input" value={c.invoice_no ?? ""}
            onChange={(e) => set({ invoice_no: e.target.value || null })} />
        </label>
        <div style={{ gridColumn: "span 2", minWidth: 0 }}>
          <ContractAttach label="Hoá đơn (scan)" docs={c.invoice_docs}
            onChange={(invoice_docs: ContractDoc[]) => set({ invoice_docs })} />
        </div>
      </div>

      <h4 style={{ margin: "14px 0 6px" }}>Thanh toán (mỗi đợt giao một lần)</h4>
      <div className="form-note" style={{ fontSize: 11.5, marginBottom: 8 }}>
        Đây là <b>ghi nhận lần thanh toán</b> — số liệu tiêu thụ và doanh thu vẫn lấy từ các dòng
        chi tiết ở trên.
      </div>
      <div style={GRID}>
        <label className="form-field">Ngày thanh toán
          <DateInput value={c.payment_date ?? ""} onChange={(v) => set({ payment_date: v || null })} />
        </label>
        <label className="form-field">Sản lượng thanh toán (tấn)
          {/* Dùng NumInput như mọi ô số khác: gõ "4,62" kiểu Việt vẫn ra 4.62 (parse thẳng bằng
              `Number` thì dấu phẩy thành NaN và ô kẹt luôn ở "NaN"). */}
          <NumInput value={c.payment_qty ?? null} onChange={(v) => set({ payment_qty: v })}
            className="blt-date-input r" placeholder="" />
        </label>
        <div style={{ gridColumn: "span 2", minWidth: 0 }}>
          <ContractAttach label="Chứng từ thanh toán" docs={c.payment_docs}
            onChange={(payment_docs: ContractDoc[]) => set({ payment_docs })} />
        </div>
      </div>
    </>
  );
}
