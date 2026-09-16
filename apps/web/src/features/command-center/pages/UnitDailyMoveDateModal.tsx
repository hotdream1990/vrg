/* Đổi NGÀY của một bản ghi đã nhập (nhập nhầm ngày) — nội dung giữ nguyên, không phải nhập lại.
   Cửa sổ sửa + chốt số liệu áp cho CẢ ngày cũ lẫn ngày mới (server ép). Tài khoản đơn vị bị chặn thì
   KHÔNG chặn cứng nữa mà chuyển sang gửi Đề nghị sửa (`daily_move`) để Ban duyệt.
   Ngày mới đã có số liệu → server từ chối, không gộp/ghi đè. */

import { SendOutlined } from "@ant-design/icons";
import { Alert, Modal, message } from "antd";
import { useEffect, useState } from "react";

import { dmy } from "../../../lib/date";
import { type MoveDateResult, moveDailyDate } from "../../../lib/unit-daily-client";
import { KIND_LABEL, type Kind } from "../../../lib/unit-daily-fields";
import { useEditRequest } from "../../../lib/use-edit-request";
import { useAuth } from "../../auth/AuthContext";
import DateInput from "../sections/DateInput";
import { dailyMoveDraft } from "./unit-daily-edit-request";

const PRICE_LABEL: Record<string, string> = {
  purchase: "đơn giá mủ nước", purchase_cup: "đơn giá mủ chén", purchase_lace: "đơn giá mủ dây",
};

const daysBetween = (later: string, earlier: string) =>
  Math.round((new Date(later + "T00:00:00").getTime() - new Date(earlier + "T00:00:00").getTime()) / 86_400_000);

type Props = {
  open: boolean;
  role: "member" | "hq";
  kind: Kind;
  company: string;
  asOf: string;              // ngày ĐANG lưu của bản ghi
  today: string;
  windowDays: number;
  isAdmin: boolean;          // admin không bị giới hạn cửa sổ sửa
  requestMode?: boolean;     // bản ghi đang khoá (chốt/cửa sổ) → mở ở chế độ đề nghị sửa
  onClose: () => void;
  onMoved: () => void;
};

export default function UnitDailyMoveDateModal(
  { open, role, kind, company, asOf, today, windowDays, isAdmin, requestMode, onClose, onMoved }: Props,
) {
  const [to, setTo] = useState(asOf);
  const [saving, setSaving] = useState(false);
  const { canEditUnitData } = useAuth();
  const { saveOrRequest, modal } = useEditRequest();
  useEffect(() => { if (open) setTo(asOf); }, [open, asOf]);

  const outOfWindow = (d: string) => !isAdmin && daysBetween(today, d) > windowDays;
  // Tài khoản đơn vị: ngày ngoài cửa sổ không còn là lỗi chặn nút — thành đề nghị gửi Ban duyệt.
  const asRequest = canEditUnitData && (!!requestMode || outOfWindow(asOf) || (!!to && outOfWindow(to)));
  const err = !to ? "Chọn ngày mới."
    : to === asOf ? "Ngày mới đang trùng ngày hiện tại."
    : to > today ? "Không chuyển sang ngày trong tương lai."
    : canEditUnitData ? ""
    : outOfWindow(to) ? `Ngày mới đã ngoài cửa sổ nhập (${windowDays} ngày gần nhất).`
    : outOfWindow(asOf) ? `Ngày hiện tại của bản ghi đã ngoài cửa sổ nhập (${windowDays} ngày gần nhất) — không sửa được nữa.`
    : "";

  const submit = async () => {
    setSaving(true);
    try {
      const out: { res?: MoveDateResult } = {};
      const result = await saveOrRequest(
        async () => { out.res = await moveDailyDate(role, kind, company, asOf, to); },
        dailyMoveDraft(kind, company, asOf, to));
      if (result === "cancelled") return;
      if (result === "requested" || !out.res) { onClose(); return; }   // popup đã báo, số liệu chưa đổi
      const res = out.res;
      const moved = res.moved_prices.map((p) => PRICE_LABEL[p] ?? p);
      // Soạn như đề nghị mà server vẫn cho chuyển thẳng (hàng rào đã mở) → nói rõ là không cần Ban duyệt.
      message.success(`Đã chuyển ${asRequest ? "trực tiếp " : ""}số liệu sang ngày ${dmy(to)}`
        + (moved.length ? ` (kèm ${moved.join(", ")})` : ""));
      // Ngày mới đã có đơn giá riêng → giữ số của ngày đó, báo để người dùng tự đối chiếu.
      res.kept_prices.forEach((p) => message.warning(
        `Ngày ${dmy(to)} đã có ${PRICE_LABEL[p] ?? p} — giữ nguyên số của ngày đó, không ghi đè.`));
      onMoved();
      onClose();
    } catch (e) {
      message.error((e as Error).message);
    } finally { setSaving(false); }
  };

  return (
    <Modal open={open} onCancel={onClose} width={520} destroyOnHidden
           title={`Đổi ngày bản ghi — ${KIND_LABEL[kind]}`}
           okText={saving ? "Đang chuyển…" : asRequest ? <><SendOutlined /> Gửi đề nghị sửa</> : "Đổi ngày"}
           cancelText="Huỷ"
           okButtonProps={{ disabled: !!err || saving }} onOk={submit}>
      <p style={{ marginTop: 0 }}>
        <b>{company}</b> · đang lưu ở ngày <b>{dmy(asOf)}</b>
      </p>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12 }}>
        <span>Chuyển sang ngày</span>
        <DateInput value={to} onChange={setTo} noFuture style={{ width: 190 }} />
      </div>
      <p className="form-note">
        Toàn bộ số liệu của bản ghi được chuyển sang ngày mới, không phải nhập lại.
        {kind === "purchase" && " Đơn giá mủ nước/mủ chén của đơn vị được chuyển kèm."}
        {" "}Ngày mới đã có số liệu thì phải xoá số ngày đó trước, hệ thống không gộp hai ngày.
      </p>
      {asRequest && !err && (
        <Alert type="warning" showIcon
               message="Bạn đang soạn đề nghị sửa — số liệu chỉ thay đổi sau khi Ban duyệt." />
      )}
      {err && <Alert type="warning" showIcon message={err} />}
      {modal}
    </Modal>
  );
}
