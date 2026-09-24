import {
  ArrowLeftOutlined, CheckCircleOutlined, DeleteOutlined, PlusOutlined, SendOutlined, UndoOutlined,
} from "@ant-design/icons";
import { Modal, Spin, Tag, message } from "antd";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  type Attachment, type SupportContext, type SupportMessage, type ThreadRow,
  deleteThread, fetchSupportContext, fetchThread, replyThread, setThreadStatus,
} from "../../../lib/support-client";
import { useAuth } from "../../auth/AuthContext";
import SupportComposer from "../sections/SupportComposer";
import { AttachmentList, AttachmentPicker } from "../sections/SupportAttachments";
import SupportMessageBody from "../sections/SupportMessageBody";
import { KIND_COLOR, KIND_LABEL, stampVN } from "../sections/support-format";
import "../../bulletin/bulletin.css";
import "../support.css";

/** Chi tiết một luồng: toàn bộ hội thoại + ô phản hồi.
 *
 *  Luồng chỉ thuộc MỘT đơn vị, nên trang này không cần lọc gì thêm — server đã trả 404 nếu
 *  tài khoản không thuộc phạm vi của luồng. */
export default function SupportThreadPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const threadId = Number(id);

  const [ctx, setCtx] = useState<SupportContext | null>(null);
  const [thread, setThread] = useState<ThreadRow | null>(null);
  const [messages, setMessages] = useState<SupportMessage[]>([]);
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [composing, setComposing] = useState(false);

  useEffect(() => { fetchSupportContext().then(setCtx).catch((e) => setErr(e.message)); }, []);

  const load = useCallback(() => {
    if (!Number.isFinite(threadId)) { setErr("Đường dẫn không hợp lệ."); setLoading(false); return; }
    setLoading(true); setErr("");
    fetchThread(threadId)
      .then((r) => { setThread(r.thread); setMessages(r.messages); })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [threadId]);
  useEffect(() => { load(); }, [load]);

  const send = async () => {
    if (!body.trim() && !files.length) { message.error("Nhập nội dung phản hồi hoặc đính kèm file."); return; }
    setBusy(true);
    try {
      await replyThread(threadId, body, files);
      setBody(""); setFiles([]);
      load();
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const toggleStatus = async () => {
    if (!thread) return;
    const next = thread.status === "open" ? "closed" : "open";
    try {
      await setThreadStatus(threadId, next);
      load();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  const remove = () => {
    Modal.confirm({
      title: "Xoá tin này?",
      content: "Xoá hẳn cả luồng và mọi phản hồi trong đó. Thao tác không hoàn tác được.",
      okText: "Xoá", okButtonProps: { danger: true }, cancelText: "Huỷ",
      onOk: async () => {
        await deleteThread(threadId);
        nav("/ho-tro");
      },
    });
  };

  if (loading || !ctx) {
    return (
      <div className="main">
        {err ? <div className="blt-error">{err}</div> : <div className="blt-loading"><Spin /> Đang tải…</div>}
      </div>
    );
  }
  if (!thread) {
    return (
      <div className="main">
        <div className="blt-error">{err || "Không tìm thấy tin."}</div>
        <button className="btn" onClick={() => nav("/ho-tro")}><ArrowLeftOutlined /> Về hộp thư</button>
      </div>
    );
  }

  const closed = thread.status === "closed";

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2>{thread.subject}</h2>
          <p>
            <Tag color={KIND_COLOR[thread.kind]}>
              {KIND_LABEL[thread.kind]}
            </Tag>
            {ctx.side === "hq" && <b style={{ marginRight: 10 }}>{thread.company}</b>}
            Mở lúc {stampVN(thread.created_at)}
            {closed && <Tag style={{ marginLeft: 8 }}>Đã đóng</Tag>}
          </p>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => nav("/ho-tro")}><ArrowLeftOutlined /> Hộp thư</button>
          {/* Khép thẻ: cả hai bên đều làm được (đơn vị cũng có quyền nói "thôi không cần nữa").
              MỞ LẠI thì chỉ Tập đoàn — bên tiếp nhận và xử lý ca. Để đơn vị tự mở lại thẻ đã khép
              là quay về đúng cái vừa bỏ: một thẻ dùng đi dùng lại cho nhiều việc. Đơn vị bấm nhầm
              thì mở thẻ mới, hoặc báo Ban mở lại hộ. */}
          {ctx.can_write && (!closed || ctx.side === "hq") && (
            <button className="btn" onClick={toggleStatus}>
              {closed ? <><UndoOutlined /> Mở lại</> : <><CheckCircleOutlined /> Đánh dấu đã xong</>}
            </button>
          )}
          {user?.role === "admin" && (
            <button className="btn" onClick={remove}><DeleteOutlined /> Xoá</button>
          )}
        </div>
      </div>

      {err && <div className="blt-error">{err}</div>}

      <div className="card sp-thread">
        {messages.map((m) => (
          <div key={m.id} className={`sp-msg ${m.side}`}>
            <div className="sp-msg-head">
              <b>{m.author_name || m.author}</b>
              <span>{m.side === "hq" ? "Tập đoàn" : thread.company}</span>
              <span>{stampVN(m.created_at)}</span>
            </div>
            {m.body && <div className="sp-msg-body"><SupportMessageBody text={m.body} /></div>}
            <AttachmentList files={m.files} />
          </div>
        ))}
      </div>

      {/* Mỗi thẻ = MỘT trường hợp. Khép rồi thì đóng ô phản hồi luôn (server cũng chặn), và mời
          mở thẻ mới ngay tại đây — để người dùng khỏi gõ xong mới bị báo lỗi. */}
      {ctx.can_write && (closed ? (
        <div className="card sp-compose">
          <h3>Trường hợp này đã khép lại</h3>
          <p className="form-note" style={{ margin: 0 }}>
            Thẻ đã khép thì không nhận thêm phản hồi. Có việc mới, vui lòng mở thẻ mới để mỗi
            trường hợp theo dõi riêng một chỗ.
          </p>
          <div>
            <button className="btn btn-primary" onClick={() => setComposing(true)}>
              <PlusOutlined /> {ctx.side === "hq" ? "Soạn thông báo mới" : "Gửi yêu cầu mới"}
            </button>
          </div>
        </div>
      ) : (
        <div className="card sp-compose">
          <h3>Phản hồi</h3>
          <textarea className="sp-textarea" rows={5} value={body} disabled={busy}
            placeholder="Nhập nội dung phản hồi…" onChange={(e) => setBody(e.target.value)} />
          <AttachmentPicker value={files} onChange={setFiles} disabled={busy} />
          <div>
            <button className="btn btn-primary" onClick={send} disabled={busy}>
              <SendOutlined /> {busy ? "Đang gửi…" : "Gửi phản hồi"}
            </button>
          </div>
        </div>
      ))}

      {composing && (
        <SupportComposer ctx={ctx} onClose={() => setComposing(false)}
          onSent={(newId) => { setComposing(false); if (newId) nav(`/ho-tro/${newId}`); else nav("/ho-tro"); }} />
      )}
    </div>
  );
}
