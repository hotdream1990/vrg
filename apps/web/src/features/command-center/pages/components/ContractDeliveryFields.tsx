import type { Contract, ContractMeta } from "../../../../lib/sales-contract-client";
import DateInput from "../../sections/DateInput";

type Props = {
  c: Contract;
  meta: ContractMeta;
  /** Đơn vị cùng nhóm công ty mẹ–con — rỗng = đơn vị đứng một mình, không có tiêu thụ nội bộ. */
  peers: string[];
  set: (patch: Partial<Contract>) => void;
};

const GRID: React.CSSProperties = {
  marginTop: 10, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))",
  gap: 10,
};

/** Các ô của MỘT LẦN GIAO: ngày giao · hình thức · đơn vị nhận (nội bộ) · nguồn tiêu thụ.
 *
 *  Dùng cho đợt giao lẫn hợp đồng giao-1-lần (hợp đồng đó chính là một lần giao). Có ngày giao =
 *  chốt thành tiêu thụ → hình thức và NGUỒN (khai thác / thu mua, 03/10/2026) mới bắt buộc; đợt
 *  mới lập chưa xuất hàng thì để trống được. Server ép đúng luật này (`sales_contract_clean`). */
export default function ContractDeliveryFields({ c, meta, peers, set }: Props) {
  const required = c.delivered_at ? " *" : "";
  return (
    <div style={GRID}>
      <label className="form-field">Ngày giao
        <DateInput value={c.delivered_at ?? ""} onChange={(v) => set({ delivered_at: v || null })} />
      </label>
      <label className="form-field">Hình thức tiêu thụ{required}
        <select className="blt-date-input" value={c.channel ?? ""}
          onChange={(e) => set({ channel: e.target.value || null, to_company: null })}>
          <option value="">— chọn hình thức —</option>
          {Object.entries(meta.channels)
            // Đơn vị đứng một mình (không thuộc nhóm mẹ–con) thì không có tiêu thụ nội bộ.
            .filter(([k]) => k !== "internal" || peers.length > 0)
            .map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </label>
      {c.channel === "internal" && (
        <label className="form-field">Đơn vị nhận
          <select className="blt-date-input" value={c.to_company ?? ""}
            onChange={(e) => set({ to_company: e.target.value || null })}>
            <option value="">— chọn đơn vị —</option>
            {peers.map((u) => <option key={u} value={u}>{u}</option>)}
          </select>
        </label>
      )}
      {/* Không chọn sẵn: đoán hộ một nguồn là lệch tiêu thụ khai thác / thu mua mà không ai hay. */}
      <label className="form-field">Nguồn tiêu thụ{required}
        <select className="blt-date-input" value={c.source ?? ""}
          onChange={(e) => set({ source: e.target.value || null })}>
          <option value="">— khai thác hay thu mua —</option>
          {Object.entries(meta.sources ?? {})
            .map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </label>
      <p className="form-note" style={{ gridColumn: "1 / -1", margin: 0, fontSize: 12 }}>
        Để trống <b>Ngày giao</b> nếu đợt mới lập, chưa xuất hàng — đợt vẫn nằm ở phần chưa giao
        của hợp đồng và chưa tính vào tiêu thụ. Điền ngày giao (chốt thành tiêu thụ) thì phải chọn
        {" "}<b>Hình thức</b> và <b>Nguồn tiêu thụ</b>: hàng từ mủ <b>khai thác</b> của đơn vị hay
        mủ <b>thu mua</b>.
        {!peers.length && <>{" "}“{c.company}” chưa thuộc nhóm công ty mẹ–con nên không có{" "}
          <b>Tiêu thụ nội bộ</b>. Gán <b>Công ty mẹ</b> ở màn Đơn vị thành viên nếu đơn vị này
          có bán nội bộ.</>}
      </p>
    </div>
  );
}
