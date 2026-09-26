import { PlusOutlined, SendOutlined } from "@ant-design/icons";
import { message } from "antd";
import { useState } from "react";

import { type Attachment, replyThread } from "../../../lib/support-client";
import { AttachmentPicker } from "./SupportAttachments";

interface SupportReplyBoxProps {
  threadId: number;
  closed: boolean;
  /** Bên đang xem là Tập đoàn — đổi nhãn nút mở thẻ mới, và không cần lời dặn phản hồi. */
  isHq: boolean;
  /** Thẻ Tập đoàn gửi xuống (thông báo · nhắc lịch · cảnh báo). */
  fromHq: boolean;
  onSent: () => void;
  onCompose: () => void;
}

/** Cuối trang chi tiết thẻ: ô phản hồi, hoặc lời mời mở thẻ mới khi thẻ đã khép.
 *
 *  Mỗi thẻ = MỘT trường hợp. Khép rồi thì đóng ô phản hồi luôn (server cũng chặn), và mời mở thẻ
 *  mới ngay tại đây — để người dùng khỏi gõ xong mới bị báo lỗi. */
export default function SupportReplyBox({
  threadId, closed, isHq, fromHq, onSent, onCompose,
}: SupportReplyBoxProps) {
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<Attachment[]>([]);
  const [busy, setBusy] = useState(false);

  const send = async () => {
    if (!body.trim() && !files.length) { message.error("Nhập nội dung phản hồi hoặc đính kèm file."); return; }
    setBusy(true);
    try {
      await replyThread(threadId, body, files);
      setBody(""); setFiles([]);
      onSent();
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (closed) {
    return (
      <div className="card sp-compose">
        <h3>Trường hợp này đã khép lại</h3>
        <p className="form-note" style={{ margin: 0 }}>
          Thẻ đã khép thì không nhận thêm phản hồi. Có việc mới, vui lòng mở thẻ mới để mỗi
          trường hợp theo dõi riêng một chỗ.
        </p>
        <div>
          <button className="btn btn-primary" onClick={onCompose}>
            <PlusOutlined /> {isHq ? "Soạn thông báo mới" : "Gửi yêu cầu mới"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="card sp-compose">
      <h3>Phản hồi</h3>
      {/* Đơn vị không tự khép thẻ Tập đoàn gửi xuống — kết quả phải nằm ngay trong thẻ này. */}
      {!isHq && fromHq && (
        <p className="form-note" style={{ margin: 0 }}>
          Vui lòng phản hồi kết quả ngay trong thông báo này, tại ô bên dưới. Tập đoàn sẽ khép thẻ
          sau khi nhận được phản hồi.
        </p>
      )}
      <textarea className="sp-textarea" rows={5} value={body} disabled={busy}
        placeholder="Nhập nội dung phản hồi…" onChange={(e) => setBody(e.target.value)} />
      <AttachmentPicker value={files} onChange={setFiles} disabled={busy} />
      <div>
        <button className="btn btn-primary" onClick={send} disabled={busy}>
          <SendOutlined /> {busy ? "Đang gửi…" : "Gửi phản hồi"}
        </button>
      </div>
    </div>
  );
}
