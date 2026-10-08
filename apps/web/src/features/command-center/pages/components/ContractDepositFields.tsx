import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";

import { fmtCcyAmount, lineAmount } from "../../../../lib/contract-money";
import type {
  Contract, ContractDeposit, ContractDoc, ContractLine,
} from "../../../../lib/sales-contract-client";
import DateInput from "../../sections/DateInput";
import NumInput from "../../sections/NumInput";
import ContractAttach from "./ContractAttach";

type Props = {
  c: Contract;
  /** Loại tiền được chọn — cùng danh sách với dòng chi tiết (VNĐ, USD, nội tệ của đơn vị). */
  currencies: string[];
  set: (patch: Partial<Contract>) => void;
};

const ROW: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "70px repeat(3, minmax(150px, 1fr)) minmax(260px, 2fr) 40px",
  gap: 10, alignItems: "end",
};

/** VNĐ nhập TRIỆU đồng (cùng quy ước đơn giá), ngoại tệ nhập nguyên tệ. */
export const depositUnit = (ccy: string | null | undefined) =>
  (!ccy || ccy === "VND" ? "triệu đồng" : ccy);

/** Giá trị hợp đồng theo ĐÚNG loại tiền cọc — null khi không so được (dòng khác loại tiền, thiếu
 *  giá). Khớp `contract_deposit.contract_value` ở server: cộng thành tiền TỪNG DÒNG (ngoại tệ đã làm
 *  tròn 2 số lẻ). */
export function contractValueIn(lines: ContractLine[], ccy: string): number | null {
  const filled = lines.filter((l) => l.grade || l.qty != null);
  if (!filled.length) return null;
  let total = 0;
  for (const l of filled) {
    // Giá 0 = chưa chốt giá (phụ lục theo công thức) — coi như thiếu, giống server.
    if ((l.ccy || "VND") !== ccy || l.qty == null || !l.price) return null;
    total += lineAmount(l) as number;
  }
  return total;
}

/** Loại tiền của hợp đồng khi MỌI dòng cùng một loại — null khi lẫn hoặc chưa có dòng. */
function linesCcy(lines: ContractLine[]): string | null {
  const set = new Set(lines.filter((l) => l.grade || l.qty != null).map((l) => l.ccy || "VND"));
  return set.size === 1 ? [...set][0] : null;
}

/** Loại tiền mặc định của một đợt cọc = loại tiền của hợp đồng (hợp đồng USD mà mặc định VNĐ là mời
 *  gõ 200.000 USD thành 200.000 triệu đồng). Form gửi TƯỜNG MINH loại tiền của từng đợt. */
export const defaultDepositCcy = (c: Contract): string => linesCcy(c.lines) || "VND";
const ccyOf = (d: ContractDeposit, c: Contract) => d.ccy || defaultDepositCcy(c);

/** Tổng tiền cọc theo từng loại tiền (bỏ đợt chưa có số tiền). */
function totalsByCcy(c: Contract): Map<string, number> {
  const out = new Map<string, number>();
  for (const d of c.deposits ?? []) {
    if (d.amount == null) continue;
    const k = ccyOf(d, c);
    out.set(k, (out.get(k) ?? 0) + d.amount);
  }
  return out;
}

/** Tổng cọc một loại tiền vượt giá trị hợp đồng — gần như chắc chắn gõ ĐỒNG vào ô TRIỆU đồng.
 *  Trả về loại tiền bị vượt (null = không vượt). Server cũng chặn. */
export function depositTooLarge(c: Contract): string | null {
  for (const [ccy, total] of totalsByCcy(c)) {
    const value = contractValueIn(c.lines, ccy);
    if (value != null && total > value + 1e-6) return ccy;
  }
  return null;
}

/** Thân gửi lên: loại tiền từng đợt gửi tường minh, đợt chưa có số tiền thì không mang loại tiền. */
export const depositsOut = (c: Contract): ContractDeposit[] =>
  (c.deposits ?? []).map((d) => ({ ...d, ccy: d.amount != null ? ccyOf(d, c) : null }));

/** Đợt cọc có ngày sau hôm nay (giờ MÁY người dùng — 0h–7h sáng ở VN, UTC vẫn là hôm trước). */
export const futureDepositIndex = (c: Contract): number => {
  const today = new Date().toLocaleDateString("sv-SE");
  return (c.deposits ?? []).findIndex((d) => !!d.date && d.date > today);
};

/** Phần trăm cọc / giá trị hợp đồng (tiền thì dùng `fmtCcyAmount`). */
const n2 = (v: number) => v.toLocaleString("vi-VN", { maximumFractionDigits: 2 });
const EMPTY_DEPOSIT: ContractDeposit = { amount: null, ccy: null, date: null, docs: [] };

/** ĐẶT CỌC của hợp đồng — NHIỀU ĐỢT CỌC, mỗi đợt: số tiền · loại tiền · ngày cọc · chứng từ (scan).
 *  Chỉ ở hợp đồng — khoản cọc gắn với hợp đồng, không thuộc từng đợt giao. */
export default function ContractDepositFields({ c, currencies, set }: Props) {
  const rows = c.deposits ?? [];
  const put = (i: number, patch: Partial<ContractDeposit>) =>
    set({ deposits: rows.map((d, k) => (k === i ? { ...d, ...patch } : d)) });
  const totals = totalsByCcy(c);
  const over = depositTooLarge(c);
  const contractCcy = linesCcy(c.lines);
  const mismatch = [...totals.keys()].find((k) => contractCcy != null && k !== contractCcy);
  return (
    <>
      <h4 style={{ margin: "14px 0 6px" }}>Đặt cọc</h4>
      {rows.length === 0 && (
        <div style={{ color: "var(--muted)", fontSize: 12.5, marginBottom: 6 }}>Chưa có đợt cọc nào.</div>
      )}
      <div style={{ display: "grid", gap: 8 }}>
        {rows.map((d, i) => {
          const ccy = ccyOf(d, c);
          return (
            <div key={i} style={ROW}>
              <b style={{ paddingBottom: 8 }}>Đợt {i + 1}</b>
              <label className="form-field">Số tiền cọc ({depositUnit(ccy)})
                <NumInput value={d.amount ?? null} className="blt-date-input r" placeholder=""
                  onChange={(v) => put(i, { amount: v })} />
              </label>
              <label className="form-field">Loại tiền
                <select className="blt-date-input" value={ccy}
                  onChange={(e) => put(i, { ccy: e.target.value })}>
                  {currencies.map((k) => <option key={k} value={k}>{k}</option>)}
                </select>
              </label>
              <label className="form-field">Ngày cọc
                <DateInput value={d.date ?? ""} onChange={(v) => put(i, { date: v || null })} />
              </label>
              <div style={{ minWidth: 0 }}>
                <ContractAttach label="Chứng từ cọc (scan)" docs={d.docs ?? []}
                  onChange={(docs: ContractDoc[]) => put(i, { docs })} />
              </div>
              <button className="btn" title={`Xoá đợt cọc ${i + 1}`} style={{ marginBottom: 2 }}
                onClick={() => set({ deposits: rows.filter((_, k) => k !== i) })}>
                <DeleteOutlined />
              </button>
            </div>
          );
        })}
      </div>
      <button className="btn" style={{ marginTop: 8 }}
        onClick={() => set({ deposits: [...rows, { ...EMPTY_DEPOSIT, ccy: defaultDepositCcy(c) }] })}>
        <PlusOutlined /> Thêm đợt cọc
      </button>
      {over ? (
        <div className="blt-error" style={{ marginTop: 6 }}>
          Tổng tiền cọc ({fmtCcyAmount(totals.get(over) as number, over)} {depositUnit(over)}) lớn hơn
          giá trị hợp đồng ({fmtCcyAmount(contractValueIn(c.lines, over) as number, over)}{" "}
          {depositUnit(over)}) — kiểm lại đơn vị tính:
          VNĐ nhập theo <b>triệu đồng</b>.
        </div>
      ) : (
        <p className="form-note" style={{ fontSize: 11.5, margin: "6px 0 0" }}>
          Mỗi lần nhận cọc thêm một <b>đợt cọc</b>. Tiền VNĐ nhập theo <b>triệu đồng</b> (ví dụ cọc
          500 triệu → gõ 500).
          {[...totals].map(([k, t]) => {
            const value = contractValueIn(c.lines, k);
            return (
              <span key={k}> Tổng cọc <b>{fmtCcyAmount(t, k)} {depositUnit(k)}</b>
                {value ? <> = <b>{n2((t / value) * 100)}%</b> giá trị hợp đồng</> : null}.</span>
            );
          })}
          {mismatch && <> Hợp đồng bán bằng <b>{contractCcy}</b> mà có đợt cọc ghi <b>{mismatch}</b> —
            kiểm lại loại tiền.</>}
        </p>
      )}
    </>
  );
}
