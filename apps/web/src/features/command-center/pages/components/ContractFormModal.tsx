import { Modal } from "antd";
import { useMemo, useState } from "react";

import {
  type Contract,
  type ContractLine,
  type ContractMeta,
  type ContractType,
  MAX_OVER_RATIO,
  saveContract,
} from "../../../../lib/sales-contract-client";
import CustomerPicker from "../../sections/CustomerPicker";
import DateInput from "../../sections/DateInput";
import ContractAttach from "./ContractAttach";
import ContractBatchDocs from "./ContractBatchDocs";
import ContractLinesTable, { EMPTY_LINE } from "./ContractLinesTable";

type Props = {
  meta: ContractMeta;
  /** Có giá trị = đang thêm/sửa ĐỢT GIAO của hợp đồng này. */
  parent?: Contract | null;
  /** Tổng sản lượng các đợt giao KHÁC của hợp đồng (không tính đợt đang sửa). */
  otherQty?: number;
  initial?: Contract | null;
  onClose: () => void;
  onSaved: () => void;
};

const today = () => new Date().toISOString().slice(0, 10);

const blank = (company: string): Contract => ({
  id: null, company, parent_id: null, code: "", customer_id: null, delivery_type: "single",
  contract_type: null,
  sign_date: today(), expiry_date: null, start_date: null, lines: [{ ...EMPTY_LINE }],
  delivered: false, delivered_at: null, channel: null, to_company: null,
  invoice_no: null, invoice_docs: [],
  payment_date: null, payment_qty: null, payment_docs: [], files: [], note: null,
  completed_at: null, qty: 0, qty_dry: 0, revenue: null,
});

const sumQty = (lines: ContractLine[]) => lines.reduce((s, l) => s + (l.qty ?? 0), 0);

/** Tổng thành tiền quy về ĐỒNG. null khi CÓ dòng ngoại tệ thiếu tỷ giá — giống `total_revenue_vnd`
 *  ở server: thiếu dữ kiện thì báo "—", không lặng lẽ coi là 0. */
function sumAmountVnd(lines: ContractLine[]): number | null {
  let total = 0;
  for (const l of lines) {
    if (l.qty == null || l.price == null) continue;
    if (l.ccy === "VND") total += l.qty * l.price * 1_000_000;
    else if (l.fx) total += l.qty * l.price * l.fx;
    else return null;
  }
  return total;
}
const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });

/** Modal thêm/sửa HỢP ĐỒNG hoặc ĐỢT GIAO (mỗi đợt = 1 lần giao + 1 lần thanh toán). */
export default function ContractFormModal({ meta, parent, otherQty = 0, initial, onClose, onSaved }: Props) {
  const isChild = !!parent;
  const [c, setC] = useState<Contract>(() => {
    if (initial) {
      // Bản ghi cũ có thể mang quy khô ở chủng loại KHÔNG dùng quy khô (trước đây ô này hiện cho
      // mọi dòng). Dọn ngay khi mở form — không thì ô đã ẩn, người dùng không xoá được mà lưu lại
      // bị chặn, kẹt không biết sửa ở đâu.
      const okDry = new Set(meta.dry_required);
      const lines = (initial.lines.length ? initial.lines : [{ ...EMPTY_LINE }])
        .map((l) => (okDry.has(l.grade) ? l : { ...l, qty_dry: null }));
      return { ...initial, lines };
    }
    const base = blank(parent?.company ?? meta.units[0] ?? "");
    // Đợt giao không có ngày ký riêng: form không hiện ô đó, gửi kèm ngày mặc định (hôm nay) là
    // server tưởng đợt được "ký" hôm nay rồi chặn mọi ngày giao trong quá khứ.
    return isChild ? { ...base, parent_id: parent!.id, sign_date: null } : base;
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const set = (patch: Partial<Contract>) => setC((prev) => ({ ...prev, ...patch }));
  // Đợt CHỈ tính là đã giao khi có NGÀY GIAO. Chưa có = đang chờ giao (vẫn nằm trong phần chưa
  // giao của hợp đồng), lúc đó chưa ép quy khô / hình thức tiêu thụ vì hàng chưa bán ra.
  const isDelivery = !!c.delivered_at;
  // Bản ghi này có phải MỘT LẦN GIAO không: đợt giao, hoặc hợp đồng giao trọn 1 lần.
  const isBatch = isChild || c.delivery_type === "single";
  // Đơn vị nhận hàng nội bộ = các đơn vị CÙNG NHÓM công ty mẹ–con. Rỗng = đơn vị đứng một mình,
  // không có tiêu thụ nội bộ (server cũng chặn, xem `_assert_same_group`).
  const peers = useMemo(
    () => meta.internal_targets?.[c.company] ?? [], [meta.internal_targets, c.company]);
  // Q10: trong nước bán VNĐ (+USD khi xuất khẩu); nước ngoài thêm NỘI TỆ CỦA CHÍNH đơn vị đó.
  // Hiện cả LAK lẫn KHR cho mọi đơn vị là mời người dùng chọn nhầm loại tiền.
  const currencies = useMemo(() => {
    const local = meta.unit_currency?.[c.company];
    return local && local !== "VND" ? ["VND", "USD", local] : ["VND", "USD"];
  }, [meta.unit_currency, c.company]);

  const qty = sumQty(c.lines);
  const amountVnd = sumAmountVnd(c.lines);
  // Sản lượng thực giao được phép LỆCH so với hợp đồng (cân hàng, hao hụt): vượt thì cảnh báo,
  // quá trần 110% mới chặn — đúng như server (`repo.MAX_OVER_RATIO`).
  const signed = parent?.qty ?? 0;
  const left = Math.max(0, signed - otherQty);          // còn theo đúng hợp đồng
  const cap = isChild ? signed * MAX_OVER_RATIO - otherQty : Infinity;
  const overCap = isChild && qty > cap + 1e-9;
  const overSigned = isChild && !overCap && qty > left + 1e-9;

  /** Kiểm TẤT CẢ ô bắt buộc trong một lượt, trả danh sách lỗi để hiện cùng lúc. */
  const problems = (): string[] => {
    const p: string[] = [];
    if (!c.company) p.push("Chọn đơn vị.");
    if (!c.code.trim()) p.push(isChild ? "Nhập số đợt giao." : "Nhập số hợp đồng.");
    if (!isChild && !c.customer_id) p.push("Chọn khách hàng.");
    if (!isChild && !c.sign_date) p.push("Chọn ngày ký.");
    if (isDelivery && !c.channel) p.push("Chọn hình thức tiêu thụ.");
    if (c.channel === "internal" && !c.to_company) p.push("Chọn đơn vị nhận hàng.");
    const rows = c.lines.filter((l) => l.grade || l.qty != null);
    if (!rows.length) p.push("Thêm ít nhất một dòng chi tiết.");
    rows.forEach((l, i) => {
      const at = `Dòng ${i + 1}`;
      if (!l.grade) p.push(`${at}: chọn chủng loại.`);
      if (l.qty == null || l.qty <= 0) p.push(`${at}: số lượng phải lớn hơn 0.`);
      if (isDelivery && meta.dry_required.includes(l.grade) && !l.qty_dry) {
        p.push(`${at} (${l.grade}): nhập quy khô.`);
      }
      if (l.ccy !== "VND" && !l.fx) p.push(`${at}: bán bằng ${l.ccy} thì phải nhập tỷ giá.`);
    });
    if (overCap) p.push(`Giảm sản lượng đợt giao xuống tối đa ${t3(Math.max(0, cap))} tấn.`);
    return p;
  };

  const submit = async () => {
    const p = problems();
    if (p.length) { setErr(p.join(" · ")); return; }
    setBusy(true); setErr("");
    try {
      await saveContract({
        ...c,
        lines: c.lines.filter((l) => l.grade || l.qty != null),
        parent_id: isChild ? parent!.id : null,
      } as unknown as Record<string, unknown>);
      onSaved(); onClose();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  const title = isChild
    ? `${initial ? "Sửa" : "Thêm"} đợt giao — HĐ ${parent!.code}`
    : `${initial ? "Sửa" : "Thêm"} hợp đồng`;

  // Modal rộng để dòng chi tiết đủ chỗ nằm một hàng; `min()` giữ mép modal không tràn ra ngoài
  // màn hình hẹp — số cứng 1280 sẽ vượt khung ở laptop 13".
  return (
    <Modal open width="min(1280px, 94vw)" title={title} onCancel={onClose} okText="Lưu" cancelText="Đóng"
      onOk={submit} okButtonProps={{ loading: busy, disabled: overCap }} destroyOnHidden>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))", gap: 10 }}>
        <label className="form-field">Đơn vị
          <select className="blt-date-input" value={c.company} disabled={isChild || !!initial}
            onChange={(e) => set({
              company: e.target.value, customer_id: null,
              // Đổi đơn vị là đổi luôn NHÓM mẹ–con → đơn vị nhận cũ có thể không còn cùng nhóm.
              ...(c.channel === "internal" ? { channel: null, to_company: null } : {}),
              lines: c.lines.map((l) => ({ ...l, ccy: "VND", fx: null })),
            })}>
            {meta.units.map((u) => <option key={u} value={u}>{u}</option>)}
          </select>
        </label>
        <label className="form-field">{isChild ? "Số đợt giao *" : "Số hợp đồng *"}
          <input className="blt-date-input" value={c.code}
            onChange={(e) => set({ code: e.target.value })} />
        </label>
        {!isChild && (
          <>
            <label className="form-field">Khách hàng *
              {/* Chỉ tìm trong danh mục CỦA ĐƠN VỊ đang chọn — server cũng chặn gán khách của
                  đơn vị khác (xem `sales_contract_repo.save`). */}
              <CustomerPicker width="100%" company={c.company} placeholder="Gõ để tìm khách hàng"
                value={c.customer_id ? [c.customer_id] : []}
                onChange={(ids) => set({ customer_id: ids[0] ?? null })} />
            </label>
            {/* Loại HỢP ĐỒNG là chỉ tiêu của báo cáo (dài hạn/chuyến) — KHÁC loại GIAO bên dưới:
                một hợp đồng dài hạn vẫn có thể giao trọn 1 lần. Đơn vị có hợp đồng khung thì nhập
                MỖI PHỤ LỤC NHƯ MỘT HỢP ĐỒNG và chọn "HĐ dài hạn" ở đây. */}
            <label className="form-field">Loại hợp đồng *
              <select className="blt-date-input" value={c.contract_type ?? ""}
                onChange={(e) => set({ contract_type: (e.target.value || null) as ContractType })}>
                <option value="">— chọn loại hợp đồng —</option>
                {Object.entries(meta.contract_types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label className="form-field">Loại giao
              <select className="blt-date-input" value={c.delivery_type} disabled={!!initial}
                onChange={(e) => set({ delivery_type: e.target.value as "single" | "multi" })}>
                {Object.entries(meta.delivery_types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label className="form-field">Ngày ký *
              <DateInput value={c.sign_date ?? ""} onChange={(v) => set({ sign_date: v || null })} />
            </label>
            <label className="form-field">Thời hạn hợp đồng
              <DateInput value={c.expiry_date ?? ""} onChange={(v) => set({ expiry_date: v || null })} />
            </label>
          </>
        )}
      </div>

      {!isChild && (
        <p className="form-note" style={{ fontSize: 11.5, margin: "6px 0 0" }}>
          Hệ thống <b>không quản lý hợp đồng khung</b>: đơn vị có hợp đồng dài hạn thì nhập{" "}
          <b>mỗi phụ lục như một hợp đồng</b> và chọn loại <b>HĐ dài hạn</b> để phân biệt.
          {initial && <> Đổi <b>loại giao</b> bằng nút <b>Chuyển sang giao nhiều lần</b> ở màn chi
            tiết hợp đồng — lần giao đã nhập sẽ tự thành đợt giao đầu tiên, không phải nhập lại.</>}
        </p>
      )}

      {isBatch && (
        <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))", gap: 10 }}>
          <label className="form-field">Ngày giao
            <DateInput value={c.delivered_at ?? ""} onChange={(v) => set({ delivered_at: v || null })} />
          </label>
          <label className="form-field">Hình thức tiêu thụ{isDelivery ? " *" : ""}
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
          <p className="form-note" style={{ gridColumn: "1 / -1", margin: 0, fontSize: 12 }}>
            Để trống <b>Ngày giao</b> nếu đợt mới lập, chưa xuất hàng — đợt vẫn nằm ở phần chưa giao
            của hợp đồng và chưa tính vào tiêu thụ.
            {!peers.length && <>{" "}“{c.company}” chưa thuộc nhóm công ty mẹ–con nên không có{" "}
              <b>Tiêu thụ nội bộ</b>. Gán <b>Công ty mẹ</b> ở màn Đơn vị thành viên nếu đơn vị này
              có bán nội bộ.</>}
          </p>
        </div>
      )}

      <h4 style={{ margin: "14px 0 6px" }}>Chi tiết {isChild ? "đợt giao" : "hợp đồng"}</h4>
      <ContractLinesTable lines={c.lines} meta={meta} requireDry={isDelivery}
        currencies={currencies} onChange={(lines) => set({ lines })} />

      {/* Tổng của cả hợp đồng/đợt giao — quy về VNĐ để cộng được các dòng khác loại tiền.
          Thiếu tỷ giá thì để "—" (KHÔNG coi là 0), đúng cách báo cáo đang làm. */}
      <div style={{ marginTop: 8, fontSize: 13 }}>
        Tổng sản lượng: <b>{t3(qty)}</b> tấn · <b>Thành tiền:</b>{" "}
        <b>{amountVnd == null ? "—" : `${t3(amountVnd / 1_000_000)} triệu đồng`}</b>
        {amountVnd == null && (
          <span className="form-note" style={{ marginLeft: 8, fontSize: 11.5 }}>
            (có dòng bán ngoại tệ chưa nhập tỷ giá)
          </span>
        )}
      </div>

      {isChild && (
        <>
          <div style={{ marginTop: 4, fontSize: 13 }}>
            Còn phải giao theo hợp đồng: <b>{t3(left)}</b> tấn · tối đa nhập được{" "}
            <b style={{ color: overCap ? "var(--danger)" : undefined }}>{t3(Math.max(0, cap))}</b> tấn
            <span style={{ color: "var(--muted)" }}> (trần {Math.round(MAX_OVER_RATIO * 100)}% sản lượng hợp đồng)</span>
          </div>
          {overSigned && (
            <div className="chip warn" style={{ marginTop: 6 }}>
              Tổng đã giao sẽ vượt hợp đồng {t3(qty + otherQty - signed)} tấn
              {signed > 0 && ` (+${(((qty + otherQty) / signed - 1) * 100).toFixed(1)}%)`} — vẫn lưu
              được, kiểm lại số cân trước khi lưu.
            </div>
          )}
          {overCap && (
            <div className="blt-error" style={{ marginTop: 6 }}>
              Vượt quá {Math.round(MAX_OVER_RATIO * 100)}% sản lượng hợp đồng — giảm số lượng, hoặc
              sửa sản lượng trên hợp đồng nếu hai bên đã thống nhất tăng.
            </div>
          )}
        </>
      )}

      {isBatch && <ContractBatchDocs c={c} set={set} />}

      {/* Đợt giao vẫn giữ ô đính kèm chung: các đợt chuyển từ cách nhập cũ có sẵn file ở đây,
          ẩn đi là người dùng không xem/gỡ được nữa. */}
      <div style={{ marginTop: 12 }}>
        <ContractAttach label={isChild ? "Hồ sơ khác của đợt giao" : "Hợp đồng đã ký (scan)"}
          docs={c.files} onChange={(files) => set({ files })} />
      </div>

      <label className="form-field" style={{ marginTop: 10, display: "block" }}>Ghi chú
        <input className="blt-date-input" style={{ width: "100%" }} value={c.note ?? ""}
          onChange={(e) => set({ note: e.target.value || null })} />
      </label>

      {err && <div className="blt-error" style={{ marginTop: 8 }}>{err}</div>}
    </Modal>
  );
}
