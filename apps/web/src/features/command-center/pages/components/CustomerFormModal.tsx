import { Modal } from "antd";
import { useState } from "react";

import { type Customer, saveCustomer } from "../../../../lib/sales-contract-client";

type Props = {
  units: string[];
  /** Có giá trị = đang SỬA khách hàng này; không có = thêm mới. */
  initial?: Customer | null;
  /** Đơn vị chọn sẵn khi thêm mới (giữ đơn vị của lần thêm trước cho đỡ phải chọn lại). */
  defaultCompany?: string;
  onClose: () => void;
  onSaved: (company: string) => void;
};

const blank = (company: string): Customer =>
  ({ id: null, company, code: "", name: "", tax_code: "", note: "", is_active: true });

/** Thêm/sửa khách hàng của MỘT đơn vị. Tách ra modal thay vì form ghi thẳng trên trang: danh mục
 *  là của từng đơn vị nên ô "Đơn vị" phải chọn có ý thức, dễ bấm nhầm khi form luôn mở sẵn. */
export default function CustomerFormModal({ units, initial, defaultCompany, onClose, onSaved }: Props) {
  const [c, setC] = useState<Customer>(() => initial ?? blank(defaultCompany || units[0] || ""));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (patch: Partial<Customer>) => setC((v) => ({ ...v, ...patch }));

  const submit = async () => {
    if (!c.company) { setErr("Chọn đơn vị sở hữu danh mục."); return; }
    if (!c.name.trim()) { setErr("Nhập tên khách hàng."); return; }
    setBusy(true); setErr("");
    try {
      await saveCustomer({
        id: c.id, company: c.company, code: c.code || null, name: c.name.trim(),
        tax_code: c.tax_code || null, note: c.note || null, is_active: c.is_active,
      });
      onSaved(c.company);
      onClose();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  return (
    <Modal open width="min(640px, 94vw)" title={initial ? "Sửa khách hàng" : "Thêm khách hàng"}
      onCancel={onClose} okText="Lưu" cancelText="Đóng" onOk={submit}
      okButtonProps={{ loading: busy, disabled: !c.name.trim() }} destroyOnHidden>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 10 }}>
        <label className="form-field" style={{ gridColumn: "1 / -1" }}>Đơn vị *
          {/* Đổi đơn vị của khách đã tạo = chuyển khách sang danh mục khác, kéo theo mọi hợp đồng
              đang gắn → khoá khi sửa, muốn đổi thì tạo khách mới ở đơn vị kia. */}
          <select className="blt-date-input" value={c.company} disabled={c.id != null}
            onChange={(e) => set({ company: e.target.value })}>
            {units.map((u) => <option key={u} value={u}>{u}</option>)}
          </select>
        </label>
        <label className="form-field" style={{ gridColumn: "1 / -1" }}>Tên khách hàng *
          <input className="blt-date-input" value={c.name} placeholder="vd: Công ty TNHH ABC"
            autoFocus onChange={(e) => set({ name: e.target.value })} />
        </label>
        <label className="form-field">Mã KH
          <input className="blt-date-input" value={c.code ?? ""}
            onChange={(e) => set({ code: e.target.value })} />
        </label>
        <label className="form-field">Mã số thuế
          <input className="blt-date-input" value={c.tax_code ?? ""}
            onChange={(e) => set({ tax_code: e.target.value })} />
        </label>
        <label className="form-field" style={{ gridColumn: "1 / -1" }}>Ghi chú
          <input className="blt-date-input" value={c.note ?? ""}
            onChange={(e) => set({ note: e.target.value })} />
        </label>
      </div>

      <p className="form-note" style={{ fontSize: 12, marginTop: 10 }}>
        Lưu ý: danh mục tách riêng theo đơn vị nên trùng tên giữa hai đơn vị là bình thường; trong
        cùng một đơn vị thì không được trùng tên. Khách đã gắn hợp đồng chỉ ẩn được, không xoá.
      </p>
      {err && <div className="blt-error" style={{ marginTop: 8 }}>{err}</div>}
    </Modal>
  );
}
