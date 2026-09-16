import { CheckOutlined, CloseOutlined } from "@ant-design/icons";
import { Checkbox, Input, Modal } from "antd";
import { useState } from "react";

import { dmy } from "../../../lib/date";
import type { EditRequest, EditRequestUnlock } from "../../../lib/edit-request-client";

const REJECT_NOTE_MIN = 3;

type Props = {
  mode: "approve" | "reject";
  request: EditRequest;
  willUnlock: EditRequestUnlock[];
  /** Số liệu đã đổi kể từ lúc đơn vị gửi → Duyệt phải tick xác nhận ghi đè. */
  changedSinceSubmit: boolean;
  /** Trang gọi API và tự bắt lỗi (hiện Alert đỏ trên trang, đóng popup). */
  onSubmit: (note: string, acceptChanged: boolean) => Promise<void>;
  onClose: () => void;
};

/** Popup Duyệt (ghi chú tuỳ chọn, nêu rõ đợt chốt sẽ gỡ) / Từ chối (ghi chú bắt buộc). */
export default function EditRequestReviewModal({ mode, request, willUnlock, changedSinceSubmit, onSubmit, onClose }: Props) {
  const [note, setNote] = useState("");
  const [acceptChanged, setAcceptChanged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const approve = mode === "approve";
  const needAccept = approve && changedSinceSubmit;

  const submit = async () => {
    if (!approve && note.trim().length < REJECT_NOTE_MIN) {
      setErr(`Nhập lý do từ chối (ít nhất ${REJECT_NOTE_MIN} ký tự).`);
      return;
    }
    setBusy(true); setErr("");
    try {
      await onSubmit(note, needAccept && acceptChanged);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open width="min(600px, 94vw)" destroyOnHidden maskClosable={false}
      title={approve ? "Duyệt đề nghị sửa số liệu?" : "Từ chối đề nghị sửa số liệu"}
      onCancel={busy ? undefined : onClose} onOk={submit} cancelText="Đóng"
      okText={approve ? <><CheckOutlined /> Duyệt và ghi số liệu</> : <><CloseOutlined /> Từ chối</>}
      okButtonProps={{ loading: busy, danger: !approve, disabled: needAccept && !acceptChanged }}>
      <p style={{ marginTop: 0 }}>
        <b>{request.title}</b> — {request.company}
      </p>
      {approve ? (
        <div className="form-note" style={{ fontSize: 13, display: "grid", gap: 6, marginBottom: 12 }}>
          <div>Hệ thống sẽ ghi nội dung đề nghị vào số liệu thật của đơn vị (không hoàn tác tự động).</div>
          {willUnlock.length > 0 ? (
            <div>
              Sẽ gỡ xác nhận chốt của đơn vị ở đợt chốt đến hết{" "}
              <b>{willUnlock.map((u) => dmy(u.lock_date)).join(", ")}</b> — đơn vị phải rà lại và xác nhận chốt lần nữa.
            </div>
          ) : (
            <div>Không có đợt chốt nào của đơn vị bị gỡ.</div>
          )}
          {needAccept && (
            <div>
              Số liệu đã thay đổi kể từ lúc đơn vị gửi đề nghị — duyệt sẽ ghi đè phần đang lưu bằng nội dung đề nghị.
            </div>
          )}
        </div>
      ) : (
        <div className="form-note" style={{ fontSize: 13, marginBottom: 12 }}>
          Số liệu giữ nguyên. Ghi chú được gửi email cho người gửi đề nghị.
        </div>
      )}
      {needAccept && (
        <Checkbox checked={acceptChanged} disabled={busy} style={{ marginBottom: 12 }}
          onChange={(e) => setAcceptChanged(e.target.checked)}>
          Tôi đã xem cột Hiện tại và đồng ý ghi đè bằng nội dung đề nghị
        </Checkbox>
      )}
      {/* Chừa chỗ dưới cho bộ đếm ký tự (AntD đặt tuyệt đối dưới ô) — không đè lên nút ở chân popup. */}
      <label className="form-field" style={{ display: "block", marginBottom: 22 }}>
        {approve ? "Ghi chú (không bắt buộc)" : "Lý do từ chối *"}
        <Input.TextArea rows={3} value={note} maxLength={2000} showCount disabled={busy}
          onChange={(e) => setNote(e.target.value)} />
      </label>
      {err && <div className="blt-error" style={{ marginTop: 10 }}>{err}</div>}
    </Modal>
  );
}
