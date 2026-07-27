/* Đổi NGÀY của một bản ghi đã nhập (nhập nhầm ngày) — nội dung giữ nguyên, không phải nhập lại.
   Cửa sổ sửa áp cho CẢ ngày cũ lẫn ngày mới (server ép, đây chỉ là hàng rào mềm để báo sớm).
   Ngày mới đã có số liệu → server từ chối, không gộp/ghi đè. */

import { Alert, Modal, message } from "antd";
import { useEffect, useState } from "react";

import { dmy } from "../../../lib/date";
import { moveDailyDate } from "../../../lib/unit-daily-client";
import { KIND_LABEL, type Kind } from "../../../lib/unit-daily-fields";
import DateInput from "../sections/DateInput";

const PRICE_LABEL: Record<string, string> = {
  purchase: "đơn giá mủ nước", purchase_cup: "đơn giá mủ chén",
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
  onClose: () => void;
  onMoved: () => void;
};

export default function UnitDailyMoveDateModal(
  { open, role, kind, company, asOf, today, windowDays, isAdmin, onClose, onMoved }: Props,
) {
  const [to, setTo] = useState(asOf);
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (open) setTo(asOf); }, [open, asOf]);

  const outOfWindow = (d: string) => !isAdmin && daysBetween(today, d) > windowDays;
  const err = !to ? "Chọn ngày mới."
    : to === asOf ? "Ngày mới đang trùng ngày hiện tại."
    : to > today ? "Không chuyển sang ngày trong tương lai."
    : outOfWindow(to) ? `Ngày mới đã ngoài cửa sổ nhập (${windowDays} ngày gần nhất).`
    : outOfWindow(asOf) ? `Ngày hiện tại của bản ghi đã ngoài cửa sổ nhập (${windowDays} ngày gần nhất) — không sửa được nữa.`
    : "";

  const submit = async () => {
    setSaving(true);
    try {
      const res = await moveDailyDate(role, kind, company, asOf, to);
      const moved = res.moved_prices.map((p) => PRICE_LABEL[p] ?? p);
      message.success(`Đã chuyển số liệu sang ngày ${dmy(to)}`
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
           okText={saving ? "Đang chuyển…" : "Đổi ngày"} cancelText="Huỷ"
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
      {err && <Alert type="warning" showIcon message={err} />}
    </Modal>
  );
}
