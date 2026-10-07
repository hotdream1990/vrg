import type { Contract, ContractDoc } from "../../../../lib/sales-contract-client";
import DateInput from "../../sections/DateInput";
import ContractAttach from "./ContractAttach";

type Props = {
  c: Contract;
  set: (patch: Partial<Contract>) => void;
};

const GRID: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))", gap: 10,
};

/** CHỈ THỊ GIAO HÀNG của MỘT LẦN GIAO (hợp đồng giao 1 lần / từng đợt giao): thời gian giao ·
 *  địa điểm · scan chỉ thị. Thời gian giao là ngày KẾ HOẠCH nên chọn được ngày tương lai. */
export default function ContractInstructionFields({ c, set }: Props) {
  return (
    <>
      <h4 style={{ margin: "14px 0 6px" }}>Chỉ thị giao hàng</h4>
      <div style={GRID}>
        <label className="form-field">Thời gian giao (theo chỉ thị)
          <DateInput value={c.instruction_date ?? ""}
            onChange={(v) => set({ instruction_date: v || null })} />
        </label>
        <label className="form-field">Địa điểm giao
          <input className="blt-date-input" value={c.instruction_place ?? ""} maxLength={200}
            onChange={(e) => set({ instruction_place: e.target.value || null })} />
        </label>
        <div style={{ gridColumn: "span 2", minWidth: 0 }}>
          <ContractAttach label="Chỉ thị giao hàng (scan)" docs={c.instruction_docs ?? []}
            onChange={(instruction_docs: ContractDoc[]) => set({ instruction_docs })} />
        </div>
      </div>
    </>
  );
}
