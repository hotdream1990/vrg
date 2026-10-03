import { SendOutlined } from "@ant-design/icons";
import { Alert, Modal, message } from "antd";
import { useMemo, useState } from "react";

import {
  type Contract,
  type ContractLine,
  type ContractMeta,
  type ContractType,
  MAX_OVER_RATIO,
  saveContract,
} from "../../../../lib/sales-contract-client";
import { dmy } from "../../../../lib/date";
import { DIRECT_SAVED_IN_REQUEST_MODE, useEditRequest } from "../../../../lib/use-edit-request";
import { useAuth } from "../../../auth/AuthContext";
import CustomerPicker from "../../sections/CustomerPicker";
import DateInput from "../../sections/DateInput";
import MasterContractPicker from "../../sections/MasterContractPicker";
import CertPremiumFields from "./CertPremiumFields";
import ContractAttach from "./ContractAttach";
import ContractBatchDocs from "./ContractBatchDocs";
import ContractDeliveryFields from "./ContractDeliveryFields";
import ContractLinesTable, { EMPTY_LINE } from "./ContractLinesTable";
import { contractSaveDraft } from "./contract-edit-request";

type Props = {
  meta: ContractMeta;
  /** Có giá trị = đang thêm/sửa ĐỢT GIAO của hợp đồng này. */
  parent?: Contract | null;
  /** Tổng sản lượng các đợt giao KHÁC của hợp đồng (không tính đợt đang sửa). */
  otherQty?: number;
  initial?: Contract | null;
  /** Điền sẵn cho bản ghi MỚI (khác `initial` — cái đó là đang SỬA bản ghi có sẵn).
   *  Dùng khi mở form từ màn Hợp đồng mẹ: đã biết đơn vị + hợp đồng mẹ nên không bắt chọn lại. */
  preset?: Partial<Contract>;
  /** Bản ghi đang khoá (quá hạn sửa) — đơn vị mở form để soạn ĐỀ NGHỊ SỬA gửi Ban duyệt. */
  requestMode?: boolean;
  onClose: () => void;
  onSaved: () => void;
};

const today = () => new Date().toISOString().slice(0, 10);

const blank = (company: string): Contract => ({
  id: null, company, parent_id: null, master_id: null, code: "", customer_id: null,
  delivery_type: "single",
  contract_type: null,
  sign_date: today(), expiry_date: null, start_date: null, lines: [{ ...EMPTY_LINE }],
  delivered: false, delivered_at: null, channel: null, to_company: null, source: null,
  invoice_no: null, invoice_docs: [],
  payment_date: null, payment_qty: null, payment_docs: [], files: [], note: null,
  certs: [], premium: null, premium_ccy: null,
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
export default function ContractFormModal({
  meta, parent, otherQty = 0, initial, preset, requestMode, onClose, onSaved,
}: Props) {
  const isChild = !!parent;
  const { canEditUnitData } = useAuth();
  const { saveOrRequest, modal } = useEditRequest();
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
    const base = blank(parent?.company ?? preset?.company ?? meta.units[0] ?? "");
    // Đợt giao không có ngày ký riêng: form không hiện ô đó, gửi kèm ngày mặc định (hôm nay) là
    // server tưởng đợt được "ký" hôm nay rồi chặn mọi ngày giao trong quá khứ.
    return isChild ? { ...base, parent_id: parent!.id, sign_date: null } : { ...base, ...preset };
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (patch: Partial<Contract>) => setC((prev) => ({ ...prev, ...patch }));
  // HĐ DÀI HẠN là phụ lục của một hợp đồng mẹ → BẮT BUỘC chọn hồ sơ, cả lúc tạo lẫn lúc sửa
  // (chốt 24/08/2026). Hợp đồng dài hạn cũ chưa gắn hồ sơ sẽ phải gắn ngay lần sửa đầu tiên —
  // đây là cách dọn dần 942 bản ghi cũ trên prod.
  const needMaster = !isChild && c.contract_type === "long_term";
  // Đợt CHỈ tính là đã giao khi có NGÀY GIAO. Chưa có = đang chờ giao (vẫn nằm trong phần chưa
  // giao của hợp đồng), lúc đó chưa ép hình thức tiêu thụ vì hàng chưa bán ra. Quy khô thì ép ở
  // MỌI trạng thái — nó là cách khai sản lượng, không phải dữ kiện của lần bán.
  const isDelivery = !!c.delivered_at;
  // Bản ghi này có phải MỘT LẦN GIAO không: đợt giao, hoặc hợp đồng giao trọn 1 lần.
  const isBatch = isChild || c.delivery_type === "single";
  // "Hiệu lực từ" từng dòng: chỉ khi SỬA hợp đồng (kể cả đề nghị sửa) — lúc tạo mọi dòng theo ngày
  // ký nên form giữ tối giản; đợt giao không có ngày này (ngày của đợt là ngày giao).
  const showDates = !!initial && !isChild;
  // HĐ giao 1 lần đã giao: phần tăng phải có hiệu lực TRƯỚC ngày giao, không thì là hàng chưa ký
  // mà đã giao — server cũng chặn.
  const deliveredCap = c.delivery_type === "single" ? c.delivered_at : null;
  // Không sau THỜI HẠN hợp đồng: dòng hiệu lực khi hợp đồng đã hết hạn là cam kết không bao giờ
  // thực hiện được (thường gõ nhầm năm) — server cũng chặn.
  const maxFromDate = [deliveredCap, c.expiry_date].filter((d): d is string => !!d).sort()[0] ?? null;
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
    if (needMaster && !c.master_id) {
      p.push("Phụ lục hợp đồng mẹ phải chọn hồ sơ mẹ — chưa có thì lập ở màn Hợp đồng mẹ trước, "
             + "rồi quay lại sửa hợp đồng này.");
    }
    if (c.contract_type === "spot" && c.master_id) p.push("HĐ chuyến không có hợp đồng mẹ.");
    if (!isChild && !c.sign_date) p.push("Chọn ngày ký.");
    if (isDelivery && !c.channel) p.push("Chọn hình thức tiêu thụ.");
    if (isDelivery && !c.source) p.push("Chọn nguồn tiêu thụ (khai thác hay thu mua).");
    if (c.channel === "internal" && !c.to_company) p.push("Chọn đơn vị nhận hàng.");
    const rows = c.lines.filter((l) => l.grade || l.qty != null);
    if (!rows.length) p.push("Thêm ít nhất một dòng chi tiết.");
    rows.forEach((l, i) => {
      const at = `Dòng ${i + 1}`;
      if (!l.grade) p.push(`${at}: chọn chủng loại.`);
      if (l.qty == null || l.qty <= 0) p.push(`${at}: số lượng phải lớn hơn 0.`);
      // Quy khô ép ở MỌI trạng thái: cam kết của hợp đồng và số đã giao phải cùng một gốc số
      // (khô), nếu không thì "đã ký chưa giao" là hiệu của hai đơn vị tính khác nhau.
      if (meta.dry_required.includes(l.grade) && !l.qty_dry) {
        p.push(`${at} (${l.grade}): nhập quy khô.`);
      }
      // Tỷ giá chỉ bắt buộc khi ĐÃ có ngày giao — khớp `require_fx` ở server. Lúc ký hợp đồng
      // chưa ai biết tỷ giá ngày giao hàng.
      if (isDelivery && l.ccy !== "VND" && !l.fx) {
        p.push(`${at}: đã có ngày giao thì bán bằng ${l.ccy} phải nhập tỷ giá.`);
      }
      if (showDates && l.from_date) {
        const who = l.grade ? `${at} (${l.grade})` : at;
        if (c.sign_date && l.from_date < c.sign_date) {
          p.push(`${who}: ngày hiệu lực phải từ ngày ký ${dmy(c.sign_date)} trở đi.`);
        }
        if (c.expiry_date && l.from_date > c.expiry_date) {
          p.push(`${who}: ngày hiệu lực ${dmy(l.from_date)} sau thời hạn hợp đồng `
                 + `${dmy(c.expiry_date)} — gia hạn thì sửa ô Thời hạn hợp đồng trước.`);
        }
        if (deliveredCap && l.from_date > deliveredCap) {
          p.push(`${who}: ngày giao ${dmy(deliveredCap)} trước ngày hiệu lực ${dmy(l.from_date)} — `
                 + "hợp đồng giao 1 lần chỉ giao được từ ngày hiệu lực của mọi dòng trở đi.");
        }
      }
    });
    if (overCap) p.push(`Giảm sản lượng đợt giao xuống tối đa ${t3(Math.max(0, cap))} tấn.`);
    return p;
  };

  /** "Hiệu lực từ" gửi lên: đợt giao bỏ hẳn khoá; sửa hợp đồng thì trống = null (theo ngày ký);
   *  tạo mới thì không thêm khoá — thân gửi y như cũ. Ngày TRÙNG ngày ký vẫn giữ nguyên: sửa nhầm
   *  ngày ký rồi sửa lại không được làm dòng "từ 15" lặng lẽ thành "theo ngày ký". */
  const fromDateOut = (l: ContractLine): ContractLine => {
    if (isChild) return { ...l, from_date: undefined };
    if (!showDates) return l;
    return { ...l, from_date: l.from_date || null };
  };

  const submit = async () => {
    const p = problems();
    if (p.length) { setErr(p.join(" · ")); return; }
    setBusy(true); setErr("");
    try {
      const body: Contract = {
        ...c,
        lines: c.lines.filter((l) => l.grade || l.qty != null).map(fromDateOut),
        parent_id: isChild ? parent!.id : null,
        // Đợt giao đi theo hợp đồng, KHÔNG nối thẳng vào hợp đồng mẹ (server cũng ép NULL) —
        // nối cả hai cấp là cộng đôi sản lượng đã ký của hợp đồng mẹ.
        master_id: isChild ? null : c.master_id,
      };
      // Server cho lưu thì lưu thẳng; tài khoản đơn vị bị cửa sổ sửa/chốt số liệu chặn thì popup đề nghị.
      const result = await saveOrRequest(
        () => saveContract(body as unknown as Record<string, unknown>), contractSaveDraft(body, initial));
      if (result === "cancelled") return;
      if (result === "saved") {
        // Chế độ đề nghị mà vẫn lưu thẳng được: chỉ đổi ô được phép sửa sau chốt (chứng từ, số HĐ…).
        if (requestMode) message.success(DIRECT_SAVED_IN_REQUEST_MODE);
        onSaved();
      }
      onClose();   // "requested": popup đã báo, số liệu chưa đổi nên không tải lại
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  const verb = requestMode ? "Đề nghị sửa" : initial ? "Sửa" : "Thêm";
  const title = isChild ? `${verb} đợt giao — HĐ ${parent!.code}` : `${verb} hợp đồng`;

  // Modal rộng để dòng chi tiết đủ chỗ nằm một hàng; `min()` giữ mép modal không tràn ra ngoài
  // màn hình hẹp — số cứng 1280 sẽ vượt khung ở laptop 13".
  return (
    <Modal open width="min(1280px, 94vw)" title={title} onCancel={onClose} cancelText="Đóng"
      okText={requestMode ? <><SendOutlined /> Gửi đề nghị sửa</> : "Lưu"}
      onOk={submit} okButtonProps={{ loading: busy, disabled: overCap }} destroyOnHidden>
      {requestMode && (
        <Alert type="warning" showIcon style={{ marginBottom: 10 }}
          message="Bạn đang soạn đề nghị sửa — số liệu chỉ thay đổi sau khi Ban duyệt." />
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))", gap: 10 }}>
        <label className="form-field">Đơn vị
          <select className="blt-date-input" value={c.company}
            disabled={isChild || !!initial || !!preset?.company}
            onChange={(e) => set({
              // Hợp đồng mẹ và khách hàng đều là của RIÊNG từng đơn vị → đổi đơn vị là bỏ cả hai.
              company: e.target.value, customer_id: null, master_id: null,
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
            {/* Loại HỢP ĐỒNG đứng TRƯỚC ô Hợp đồng mẹ vì chính nó quyết định ô kia có hiện hay
                không — hỏi ngược lại thì người nhập thấy một ô xuất hiện/biến mất sau lưng mình.
                KHÁC loại GIAO bên dưới: một phụ lục vẫn có thể giao trọn 1 lần. */}
            <label className="form-field">Loại hợp đồng *
              <select className="blt-date-input" value={c.contract_type ?? ""}
                onChange={(e) => {
                  const t = (e.target.value || null) as ContractType;
                  // Chuyển sang HĐ chuyến thì XOÁ hồ sơ đang chọn — ô đã khoá, giữ lại thì server
                  // chặn mà người nhập không thấy ô nào để sửa.
                  set({ contract_type: t, ...(t === "spot" ? { master_id: null } : {}) });
                }}>
                <option value="">— chọn loại hợp đồng —</option>
                {Object.entries(meta.contract_types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            {/* HỢP ĐỒNG MẸ — chỉ có nghĩa với PHỤ LỤC (nó là phụ lục của một hồ sơ mẹ).
                HĐ CHUYẾN bán đứt từng chuyến nên ô này KHÔNG hiện luôn, không phải chỉ khoá:
                một ô mờ nằm đó vẫn khiến người nhập dừng lại tự hỏi có phải mình thiếu gì không. */}
            {c.contract_type !== "spot" && (
            <label className="form-field">
              Hợp đồng mẹ (HĐNT/HĐDH){needMaster ? " *" : ""}
              <MasterContractPicker company={c.company} value={c.master_id}
                typeLabels={meta.master_types}
                // Mở từ chính màn hợp đồng mẹ thì hồ sơ đã chốt — khoá ô lại, đổi nhầm sang hồ sơ
                // khác ngay trong lúc đang xem một hồ sơ là chuyện không ai chủ ý làm.
                // Mở lại một phụ lục cũ: picker tra hợp đồng mẹ theo id rồi báo về đây để ô
                // khách hàng hiện đúng TÊN, không phải chữ "(theo hợp đồng mẹ)" trống rỗng.
                // Chọn hồ sơ CHỈ ghi liên kết, không đụng số liệu của bản ghi.
                disabled={preset?.master_id != null}
                placeholder="Gõ số hợp đồng mẹ"
                onChange={(id) => set({ master_id: id })} />
            </label>
            )}
            <label className="form-field">Khách hàng *
              {/* Chỉ tìm trong danh mục CỦA ĐƠN VỊ đang chọn — server cũng chặn gán khách của
                  đơn vị khác (xem `sales_contract_repo.save`). Nối hợp đồng mẹ KHÔNG đổi ô này:
                  hợp đồng giữ khách của chính nó (chốt 24/08/2026). */}
              <CustomerPicker width="100%" company={c.company} placeholder="Gõ để tìm khách hàng"
                value={c.customer_id ? [c.customer_id] : []}
                onChange={(ids) => set({ customer_id: ids[0] ?? null })} />
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

      {/* Mở TỪ màn hợp đồng mẹ thì hồ sơ đã chọn sẵn — nhắc "sang màn Hợp đồng mẹ mà lập" là
          chỉ đường tới nơi người dùng đang đứng. */}
      {!isChild && !preset?.master_id && (
        <p className="form-note" style={{ fontSize: 11.5, margin: "6px 0 0" }}>
          Chọn <b>Loại hợp đồng</b> trước — chính nó quyết định ô <b>Hợp đồng mẹ</b> có hiện hay
          không. <b>Phụ lục hợp đồng mẹ</b> phải chọn hồ sơ ở ô <b>Hợp đồng mẹ</b> (chưa có thì lập
          ở màn <b>Hợp đồng mẹ</b> trước); hồ sơ mẹ có thể là <b>HĐ nguyên tắc</b> hay{" "}
          <b>HĐ dài hạn</b> đều được. <b>HĐ chuyến</b> bán đứt từng chuyến nên{" "}
          <b>không có hợp đồng mẹ</b> — chọn loại đó thì ô kia không hiện. Nối hồ sơ{" "}
          <b>không đổi</b> khách hàng hay sản lượng; báo cáo xếp hợp đồng vào nhóm{" "}
          <b>HĐ nguyên tắc</b> hoặc <b>HĐ dài hạn</b> theo loại hồ sơ mẹ.
          {initial && <> Đổi <b>loại giao</b> bằng nút <b>Chuyển sang giao nhiều lần</b> ở màn chi
            tiết hợp đồng — lần giao đã nhập sẽ tự thành đợt giao đầu tiên, không phải nhập lại
            {requestMode && <>; bản ghi đang khoá thì nút đó cũng mở hộp <b>gửi đề nghị</b>, tính
              là một đề nghị riêng với đề nghị đang soạn ở đây</>}.</>}
        </p>
      )}

      {/* Sau khi đơn vị CHỐT số liệu, bản ghi KHÔNG đóng băng hoàn toàn: các ô không dịch con số
          nào vẫn sửa được (chốt 29/08/2026). Nói trước ở đây để đơn vị khỏi đi báo Ban TTKD cho
          một việc họ tự làm được. Danh sách lấy từ server — không viết tay lần hai. */}
      {initial && meta.editable_when_locked?.length > 0 && (
        <p className="form-note" style={{ fontSize: 11.5, margin: "6px 0 0" }}>
          Kể cả khi <b>số liệu đã chốt</b>, các nội dung sau vẫn sửa và lưu được bình thường:{" "}
          <b>{meta.editable_when_locked.map((f) => f.label).join(" · ")}</b>. Còn sản lượng, đơn
          giá, ngày hiệu lực của dòng, ngày giao, hình thức và nguồn tiêu thụ, khách hàng và loại hợp
          đồng là các ô làm đổi số đã báo cáo — {canEditUnitData
            ? <>bấm <b>Lưu</b>, hệ thống mở hộp gửi <b>đề nghị sửa</b>, Ban duyệt xong mới đổi.</>
            : "phải nhờ Ban TTKD sửa hộ."}
        </p>
      )}

      {isBatch && <ContractDeliveryFields c={c} meta={meta} peers={peers} set={set} />}

      <h4 style={{ margin: "14px 0 6px" }}>Chi tiết {isChild ? "đợt giao" : "hợp đồng"}</h4>
      <ContractLinesTable lines={c.lines} meta={meta} requireFx={isDelivery}
        signDate={showDates ? c.sign_date : undefined} maxFromDate={maxFromDate}
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

      {/* Hàng có chứng chỉ + premium khai ở NGỌN — nơi có sản lượng của một lần giao (chốt
          27/08/2026): HĐ chuyến / phụ lục giao 1 lần khai ngay ở đây, giao nhiều lần thì khai
          trong từng đợt giao. */}
      {isBatch && (
        <CertPremiumFields
          value={{ certs: c.certs ?? [], premium: c.premium ?? null,
                   premium_ccy: c.premium_ccy ?? null }}
          certs={meta.certs ?? []} currencies={meta.premium_currencies ?? ["USD", "VND"]}
          onChange={(patch) => set(patch)} />
      )}
      {!isBatch && (
        <div className="form-note" style={{ fontSize: 12, marginTop: 12 }}>
          Hợp đồng giao nhiều lần: <b>hàng có chứng chỉ và premium khai ở từng đợt giao</b> — mỗi
          chuyến một mức premium riêng.
        </div>
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
      {modal}
    </Modal>
  );
}
