/* Hộp "Trả về bước trước": chọn thẳng bước cần quay lại (vd lãnh đạo không duyệt tờ trình → về Nháp sửa số)
   + lý do (ghi vào lịch sử bước, hiện cho người mở bản sau). Lui không xoá gì. */

import { Input, Modal, Radio } from "antd";
import { useEffect, useState } from "react";

import { STAGES, STAGE_LABEL, type Stage } from "../../../../lib/floor-draft-flow-client";

const WHAT: Partial<Record<Stage, string>> = {
  nhap: "Sửa số phương án (FOB, nội địa). Hình dự thảo dựng lại theo số mới.",
  du_thao: "Sửa tỷ giá VCB in dưới hình dự thảo, chép/gửi lại hình.",
  to_trinh: "Sửa nội dung tờ trình.",
};

type Props = {
  open: boolean;
  stage: Stage;
  busy: boolean;
  onOk: (to: Stage, note: string) => void;
  onCancel: () => void;
};

export default function ReturnStageModal({ open, stage, busy, onOk, onCancel }: Props) {
  const earlier = STAGES.slice(0, STAGES.indexOf(stage));
  const [to, setTo] = useState<Stage>("nhap");
  const [note, setNote] = useState("");
  // Mở lại hộp: mặc định về Nháp (lý do hay gặp nhất: lãnh đạo yêu cầu đổi mức giá), xoá lý do cũ.
  useEffect(() => { if (open) { setTo(earlier[0] ?? "nhap"); setNote(""); } }, [open]);   // earlier suy từ stage

  return (
    <Modal open={open} title="Trả về bước trước để chỉnh sửa" okText={`Trả về ${STAGE_LABEL[to]}`} cancelText="Huỷ"
      confirmLoading={busy} onOk={() => onOk(to, note.trim())} onCancel={onCancel} destroyOnHidden>
      <div style={{ display: "grid", gap: 12 }}>
        <Radio.Group value={to} onChange={(e) => setTo(e.target.value)} style={{ display: "grid", gap: 8 }}>
          {earlier.map((s) => (
            <Radio key={s} value={s}>
              <b>{STAGE_LABEL[s]}</b> <span style={{ color: "var(--muted)" }}>— {WHAT[s]}</span>
            </Radio>
          ))}
        </Radio.Group>
        <label>
          <div style={{ marginBottom: 4 }}>Lý do trả về (ghi vào lịch sử)</div>
          <Input.TextArea value={note} maxLength={500} autoSize={{ minRows: 2, maxRows: 5 }}
            placeholder="vd TGĐ chưa duyệt mức +80 USD/tấn, đề nghị điều chỉnh +60" onChange={(e) => setNote(e.target.value)} />
        </label>
        <div style={{ fontSize: 12.5, color: "var(--muted)" }}>
          Không mất gì khi trả về: số, tỷ giá và nội dung tờ trình đều giữ nguyên. Số đổi thì khi lập lại tờ trình
          hệ thống nhắc soát phần nhận định cho khớp mức mới.
        </div>
      </div>
    </Modal>
  );
}
