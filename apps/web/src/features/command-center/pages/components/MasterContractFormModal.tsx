import { Modal } from "antd";
import { useState } from "react";

import {
  type MasterContract,
  type MasterType,
  saveMasterContract,
} from "../../../../lib/master-contract-client";
import type { ContractMeta } from "../../../../lib/sales-contract-client";
import CustomerPicker from "../../sections/CustomerPicker";
import DateInput from "../../sections/DateInput";
import ContractAttach from "./ContractAttach";
import MasterLinesTable, { EMPTY_MASTER_LINE } from "./MasterLinesTable";

type Props = {
  meta: ContractMeta;
  initial?: MasterContract | null;
  defaultCompany?: string;
  onClose: () => void;
  onSaved: (company: string) => void;
};

const blank = (company: string): MasterContract => ({
  id: null, company, code: "", master_type: "principle", customer_id: null,
  sign_date: null, expiry_date: null, lines: [{ ...EMPTY_MASTER_LINE }],
  price_formula: null, files: [], note: null, qty: 0,
});

const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });

/** Thêm/sửa HỢP ĐỒNG MẸ — HĐ nguyên tắc (HĐNT) / HĐ dài hạn (HĐDH).
 *
 *  Đây là HỒ SƠ GỐC ký với khách hàng: số hợp đồng · khách hàng · chủng loại kèm sản lượng cam
 *  kết · công thức giá · bản scan. KHÔNG có đơn giá — giá là số của từng chuyến (chốt 25/08/2026).
 *  Từng chuyến hàng vẫn nhập ở màn Hợp đồng rồi chọn hồ sơ này để nối vào — việc nối KHÔNG đổi
 *  số liệu nào của hợp đồng.
 */
export default function MasterContractFormModal({ meta, initial, defaultCompany, onClose, onSaved }: Props) {
  const [m, setM] = useState<MasterContract>(
    () => initial ?? blank(defaultCompany || meta.units[0] || ""));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (patch: Partial<MasterContract>) => setM((v) => ({ ...v, ...patch }));

  const qty = m.lines.reduce((s, l) => s + (l.qty ?? 0), 0);
  const qtyDry = m.lines.reduce((s, l) => s + (l.qty_dry ?? 0), 0);
  const dry = new Set(meta.dry_required);
  /** Dòng người dùng đã động vào — dòng trống bấm thêm rồi bỏ dở thì không kiểm, không lưu. */
  const filled = (l: MasterContract["lines"][number]) =>
    !!l.grade || l.qty != null || l.qty_dry != null;

  /** Kiểm mọi ô bắt buộc trong một lượt để hiện lỗi cùng lúc (giống form hợp đồng). */
  const problems = (): string[] => {
    const p: string[] = [];
    if (!m.company) p.push("Chọn đơn vị.");
    if (!m.code.trim()) p.push("Nhập số hợp đồng.");
    if (!m.customer_id) p.push("Chọn khách hàng.");
    const rows = m.lines.filter(filled);
    if (!rows.length) p.push("Thêm ít nhất một chủng loại.");
    rows.forEach((l, i) => {
      const at = `Dòng ${i + 1}`;
      if (!l.grade) p.push(`${at}: chọn chủng loại.`);
      if (l.qty != null && l.qty <= 0) p.push(`${at}: số lượng phải lớn hơn 0.`);
      // Quy khô chỉ bắt buộc khi ĐÃ cam kết số lượng — hồ sơ mẹ được phép chỉ chốt chủng loại.
      if (dry.has(l.grade) && l.qty != null && !l.qty_dry) {
        p.push(`${at} (${l.grade}): đã cam kết số lượng thì phải nhập quy khô.`);
      }
      if (l.qty != null && l.qty_dry != null && l.qty_dry > l.qty) {
        p.push(`${at} (${l.grade}): quy khô không thể lớn hơn số lượng.`);
      }
    });
    const dup = rows.map((l) => l.grade).filter((g, i, a) => g && a.indexOf(g) !== i);
    if (dup.length) p.push(`Chủng loại bị lặp: ${[...new Set(dup)].join(", ")}.`);
    return p;
  };

  const submit = async () => {
    const p = problems();
    if (p.length) { setErr(p.join(" · ")); return; }
    setBusy(true); setErr("");
    try {
      await saveMasterContract({
        ...m, lines: m.lines.filter(filled),
      } as unknown as Record<string, unknown>);
      onSaved(m.company); onClose();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  return (
    <Modal open width="min(1100px, 94vw)" destroyOnHidden
      title={initial ? `Sửa hợp đồng mẹ ${initial.code}` : "Thêm hợp đồng mẹ (HĐNT/HĐDH)"}
      onCancel={onClose} okText="Lưu" cancelText="Đóng" onOk={submit}
      okButtonProps={{ loading: busy }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))", gap: 10 }}>
        <label className="form-field">Đơn vị *
          {/* Đổi đơn vị của hồ sơ đã lưu = kéo theo cả khách hàng lẫn phụ lục sang đơn vị khác
              → khoá khi sửa, giống danh mục khách hàng. */}
          <select className="blt-date-input" value={m.company} disabled={!!initial}
            onChange={(e) => set({ company: e.target.value, customer_id: null })}>
            {meta.units.map((u) => <option key={u} value={u}>{u}</option>)}
          </select>
        </label>
        <label className="form-field">Số hợp đồng *
          <input className="blt-date-input" value={m.code} placeholder="vd: 01/2026/HĐNT-CSVN"
            onChange={(e) => set({ code: e.target.value })} />
        </label>
        <label className="form-field">Loại hợp đồng mẹ *
          {/* HĐ nguyên tắc KHÔNG có công thức giá → đổi loại là xoá luôn giá trị đang có, không
              để ô ẩn vẫn gửi chữ cũ lên server (bẫy "ô ẩn vẫn gửi giá trị mặc định"). */}
          <select className="blt-date-input" value={m.master_type}
            onChange={(e) => {
              const t = e.target.value as MasterType;
              set({ master_type: t, ...(t === "long_term" ? {} : { price_formula: null }) });
            }}>
            {Object.entries(meta.master_types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="form-field">Khách hàng *
          {/* Khách hàng của HỒ SƠ. Hợp đồng nối vào vẫn tự khai khách của chính nó — nối hồ
              sơ không đụng số liệu hợp đồng (chốt 24/08/2026). */}
          <CustomerPicker width="100%" company={m.company} placeholder="Gõ để tìm khách hàng"
            value={m.customer_id ? [m.customer_id] : []}
            onChange={(ids) => set({ customer_id: ids[0] ?? null })} />
        </label>
        <label className="form-field">Ngày ký
          <DateInput value={m.sign_date ?? ""} onChange={(v) => set({ sign_date: v || null })} />
        </label>
        <label className="form-field">Thời hạn hợp đồng
          <DateInput value={m.expiry_date ?? ""} onChange={(v) => set({ expiry_date: v || null })} />
        </label>
      </div>

      <h4 style={{ margin: "14px 0 6px" }}>Chủng loại &amp; sản lượng cam kết</h4>
      <MasterLinesTable lines={m.lines} grades={meta.grades} dryGrades={meta.dry_required}
        onChange={(lines) => set({ lines })} />
      <div style={{ marginTop: 8, fontSize: 13 }}>
        Tổng sản lượng cam kết: <b>{qty > 0 ? `${t3(qty)} tấn` : "—"}</b>
        {qtyDry > 0 && <> · Quy khô: <b>{t3(qtyDry)} tấn</b></>}
      </div>

      {/* Chỉ HĐ DÀI HẠN mới có công thức giá — HĐ nguyên tắc không có phần này. */}
      {m.master_type === "long_term" && (
        <label className="form-field" style={{ marginTop: 12, display: "block" }}>Công thức giá
          <textarea className="blt-date-input" rows={2} style={{ width: "100%", resize: "vertical" }}
            value={m.price_formula ?? ""}
            placeholder="vd: Giá SICOM TSR20 bình quân tuần trước liền kề + 30 USD/tấn, FOB HCM"
            onChange={(e) => set({ price_formula: e.target.value || null })} />
        </label>
      )}

      <div style={{ marginTop: 12 }}>
        <ContractAttach label="Hợp đồng mẹ đã ký (scan)" docs={m.files}
          onChange={(files) => set({ files })} />
      </div>

      <label className="form-field" style={{ marginTop: 10, display: "block" }}>Ghi chú
        <input className="blt-date-input" style={{ width: "100%" }} value={m.note ?? ""}
          onChange={(e) => set({ note: e.target.value || null })} />
      </label>

      {err && <div className="blt-error" style={{ marginTop: 8 }}>{err}</div>}
    </Modal>
  );
}
