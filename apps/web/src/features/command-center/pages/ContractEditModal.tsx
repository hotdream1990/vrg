/* Modal SỬA 1 hợp đồng đã ký — mở từ màn "Thống kê hợp đồng". Cho sửa MỌI trường kể cả HĐ ĐÃ GIAO
   (vốn không sửa được ở màn Báo cáo tồn kho theo ngày vì đã rớt khỏi tồn kho). XOÁ trống ô
   "Ngày giao" = MỞ LẠI về "chưa giao" → HĐ hiện lại ở Báo cáo tồn kho. Dùng lại endpoint
   saveStockContract sẵn có (member: HĐ đơn vị mình · chuyên viên: cần cap sửa). */

import { Input, Modal, Select, message } from "antd";
import { useEffect, useState } from "react";

import { FX_USD_VND, TONNES_STOCK, fxWarning, priceBound } from "../../../lib/entry-bounds";
import { CCYS, GRADES, type Ccy, priceUnitOf } from "../../../lib/unit-daily-consumption";
import { type Role, type StockContract, saveStockContract } from "../../../lib/unit-daily-client";
import { numInput } from "./unit-daily-inputs";

type Props = {
  open: boolean;
  role: Role;
  contract: StockContract | null;
  onClose: () => void;
  onSaved: () => void;
};

const num = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);

export default function ContractEditModal({ open, role, contract, onClose, onSaved }: Props) {
  const [d, setD] = useState<StockContract | null>(contract);
  const [busy, setBusy] = useState(false);
  useEffect(() => setD(contract), [contract]);
  if (!d) return null;

  const set = (p: Partial<StockContract>) => setD((cur) => (cur ? { ...cur, ...p } : cur));
  const ccy = (d.ccy ?? "VND") as Ccy;

  const save = async () => {
    setBusy(true);
    try {
      // `region` là cột ghép ở màn tra cứu, KHÔNG thuộc payload → loại ra trước khi gửi.
      const { region, ...body } = d as StockContract & { region?: unknown };
      await saveStockContract(role, d.company ?? "", body);
      message.success("Đã lưu hợp đồng.");
      onSaved();
      onClose();
    } catch (e) {
      message.error((e as Error).message || "Lưu hợp đồng thất bại.");
    } finally {
      setBusy(false);
    }
  };

  const field = (label: React.ReactNode, node: React.ReactNode) => (
    <label style={{ display: "block" }}>
      <div style={{ fontSize: 12, fontWeight: 600, opacity: 0.8, marginBottom: 3 }}>{label}</div>
      {node}
    </label>
  );
  const dateBox = (v: string | null | undefined, on: (v: string | null) => void) => (
    <input type="date" className="blt-cell-input" style={{ width: "100%" }} value={v ?? ""}
      onChange={(e) => on(e.target.value || null)} />
  );

  return (
    <Modal open={open} title={`Sửa hợp đồng${d.code ? ` — số ${d.code}` : ""}`} width={620}
      onCancel={onClose} onOk={save} confirmLoading={busy} okText="Lưu" cancelText="Đóng"
      destroyOnClose maskClosable={false}>
      <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 12 }}>
        Đơn vị: <b>{d.company}</b>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {field("Chủng loại", (
          <Select style={{ width: "100%" }} value={d.grade || undefined} showSearch placeholder="Chủng loại"
            onChange={(v) => set({ grade: v })} options={GRADES.map((g) => ({ value: g, label: g }))} />
        ))}
        {field("Số HĐ/PL", (
          <Input value={d.code ?? ""} placeholder="Số HĐ/PL"
            onChange={(e) => set({ code: e.target.value || null })} />
        ))}
        {field("Số lượng (tấn)", numInput(num(d.qty), (v) => set({ qty: v }), false, undefined, TONNES_STOCK))}
        {field(
          <>Đơn giá <span style={{ fontWeight: 400, opacity: 0.6 }}>({priceUnitOf(ccy)})</span></>,
          numInput(num(d.price), (v) => set({ price: v }), false, undefined, priceBound(ccy)),
        )}
        {field("Loại tiền", (
          <Select style={{ width: "100%" }} value={ccy}
            onChange={(v: Ccy) => set({ ccy: v })} options={CCYS} />
        ))}
        {field("Tỷ giá (USD→VND)", ccy === "USD"
          ? numInput(num(d.fx), (v) => set({ fx: v }), false, undefined, FX_USD_VND, fxWarning(d))
          : <Input disabled value="—" />)}
        {field("Bắt đầu tồn kho", dateBox(d.start_date, (v) => set({ start_date: v ?? "" })))}
        {field("Lịch giao", dateBox(d.delivery_date, (v) => set({ delivery_date: v })))}
        {field("Ngày giao (thực tế)", dateBox(d.delivered_date, (v) => set({ delivered_date: v })))}
      </div>
      <div className="form-note" style={{ marginTop: 12, fontSize: 12 }}>
        Để <b>mở lại</b> hợp đồng về <b>“chưa giao”</b>, hãy <b>xoá trống ô “Ngày giao (thực tế)”</b> rồi bấm Lưu —
        hợp đồng sẽ hiện lại ở màn <b>Báo cáo tồn kho</b> theo ngày. Đơn giá VND nhập theo{" "}
        <b>triệu đ/tấn</b> (vd 41,3), dùng dấu phẩy cho phần thập phân.
      </div>
    </Modal>
  );
}
