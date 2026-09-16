import { SendOutlined } from "@ant-design/icons";
import { App, Input, Modal } from "antd";
import { useEffect, useState } from "react";

import { fetchLockCurrent } from "../../../lib/data-lock-client";
import { dmy } from "../../../lib/date";
import { submitEditRequest } from "../../../lib/edit-request-client";
import type { EditRequestDraft } from "../../../lib/use-edit-request";

const REASON_MIN = 5;
const REASON_MAX = 2000;

type Props = {
  draft: EditRequestDraft;
  /** Câu server báo chặn (nếu mở từ một lần lưu bị chặn) — nhắc đơn vị vì sao phải gửi đề nghị. */
  blockedMessage?: string | null;
  onSubmitted: () => void;
  onCancel: () => void;
};

/** Popup "Gửi đề nghị sửa số liệu": lý do bắt buộc + lưu ý đỏ về chốt số liệu.
 *  Nội dung đề nghị là đúng thứ đơn vị vừa sửa trên form — popup chỉ hỏi thêm lý do. */
export default function EditRequestSubmitModal({ draft, blockedMessage, onSubmitted, onCancel }: Props) {
  const { message } = App.useApp();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [lockedUntil, setLockedUntil] = useState<string | null>(null);

  const firstDate = [...draft.dates].filter(Boolean).sort()[0] ?? null;

  useEffect(() => {
    let alive = true;
    fetchLockCurrent()
      .then((r) => {
        const unit = r.units.find((u) => u.company === draft.company);
        if (alive) setLockedUntil(unit?.locked_until ?? null);
      })
      .catch(() => { if (alive) setLockedUntil(null); });
    return () => { alive = false; };
  }, [draft.company]);

  const hitsLock = Boolean(lockedUntil && firstDate && lockedUntil >= firstDate);

  const submit = async () => {
    const text = reason.trim();
    if (text.length < REASON_MIN) { setErr(`Nhập lý do chỉnh sửa (ít nhất ${REASON_MIN} ký tự).`); return; }
    setBusy(true); setErr("");
    try {
      const r = await submitEditRequest({ op: draft.op, payload: draft.payload, reason: text });
      message.success(r.replaced ? "Đã cập nhật đề nghị đang chờ duyệt." : "Đã gửi đề nghị — chờ Ban duyệt.");
      onSubmitted();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Gửi đề nghị thất bại.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open width="min(620px, 94vw)" destroyOnHidden maskClosable={false}
      title="Gửi đề nghị sửa số liệu"
      onCancel={busy ? undefined : onCancel} onOk={submit}
      okText={<><SendOutlined /> Gửi đề nghị</>} cancelText="Huỷ"
      okButtonProps={{ loading: busy }}>
      <div style={{ marginBottom: 10 }}>
        Nội dung: <b>{draft.title}</b>
        {draft.company && <> — {draft.company}</>}
      </div>
      {blockedMessage && (
        <div style={{ marginBottom: 10, color: "var(--muted)", fontSize: 13 }}>{blockedMessage}</div>
      )}
      <label className="form-field" style={{ display: "block", marginBottom: 22 }}>Lý do chỉnh sửa *
        <Input.TextArea rows={4} value={reason} maxLength={REASON_MAX} showCount disabled={busy}
          onChange={(e) => setReason(e.target.value)} />
      </label>
      <div className="form-note" style={{ marginTop: 12, fontSize: 13, display: "grid", gap: 6 }}>
        <div>Thay đổi chỉ được áp dụng sau khi Ban duyệt. Trước đó số liệu vẫn giữ nguyên.</div>
        {hitsLock ? (
          <div>
            Ngày sửa nằm trong kỳ đơn vị đã chốt (đến hết {dmy(lockedUntil)}). Khi Ban duyệt, phần chốt
            từ ngày {dmy(firstDate)} sẽ bị gỡ — đơn vị phải rà lại và xác nhận chốt số liệu lần nữa.
          </div>
        ) : (
          <div>Sau khi Ban duyệt, đơn vị tự rà lại số liệu và xác nhận chốt ở đợt chốt kế tiếp.</div>
        )}
      </div>
      {err && <div className="blt-error" style={{ marginTop: 10 }}>{err}</div>}
    </Modal>
  );
}
