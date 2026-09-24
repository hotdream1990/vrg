/* Hộp "Lưu bản nháp tờ trình" từ phương án đang sửa (Trợ lý AI). Lưu xong báo kèm lối mở bản nháp. */

import { App, Button, Input, Modal } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { type DraftSource, type Proposal, createDraft, draftPath } from "../../../../lib/floor-proposal-client";

// Hộp này có thể mở từ khung xem trước tờ trình (overlay z-index 1000) → phải nằm trên nó.
const PREVIEW_OVERLAY_Z = 1000;

type Props = {
  open: boolean;
  /** Phương án MỚI NHẤT lúc bấm lưu (chờ các lần sửa ô đang gửi xong). */
  resolveProposal: () => Promise<Proposal>;
  source: DraftSource;
  onClose: () => void;
};

export default function SaveDraftModal({ open, resolveProposal, source, onClose }: Props) {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      const proposal = await resolveProposal();
      const d = await createDraft({
        source, proposal, title: title.trim() || undefined, note: note.trim() || undefined,
      });
      const url = draftPath(d.id);
      // Thông báo nằm NGOÀI Router (antd App) → không dùng <Link>, điều hướng bằng hàm navigate.
      message.success({
        content: (
          <span>
            Đã lưu bản nháp “{d.title}”.
            <Button type="link" size="small" onClick={() => navigate(url)}>Mở bản nháp</Button>
          </span>
        ),
        duration: 6,
      });
      setTitle(""); setNote("");
      onClose();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "Không lưu được bản nháp.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} title="Lưu bản nháp tờ trình" onCancel={onClose} onOk={save}
      okText="Lưu bản nháp" cancelText="Huỷ" confirmLoading={saving} destroyOnHidden
      zIndex={PREVIEW_OVERLAY_Z + 100}>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <label>
          <div style={{ marginBottom: 4 }}>Tiêu đề</div>
          <Input value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)}
            placeholder="Để trống — hệ thống tự đặt theo ngày tờ trình" />
        </label>
        <label>
          <div style={{ marginBottom: 4 }}>Ghi chú nội bộ</div>
          <Input.TextArea value={note} maxLength={4000} autoSize={{ minRows: 2, maxRows: 6 }}
            onChange={(e) => setNote(e.target.value)} placeholder="Không in lên tờ trình" />
        </label>
        <div className="form-note" style={{ fontSize: 12.5 }}>
          Bản nháp lưu lại số thị trường tại lúc lưu. Không ghi vào biểu giá sàn chính thức.
        </div>
      </div>
    </Modal>
  );
}
