import {
  ArrowLeftOutlined, CheckCircleOutlined, DeleteOutlined, UndoOutlined,
} from "@ant-design/icons";
import { Modal, Spin, Tag, message } from "antd";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  type SupportContext, type SupportMessage, type ThreadRow,
  deleteThread, fetchSupportContext, fetchThread, setThreadStatus,
} from "../../../lib/support-client";
import { useAuth } from "../../auth/AuthContext";
import SupportComposer from "../sections/SupportComposer";
import { AttachmentList } from "../sections/SupportAttachments";
import SupportMessageBody from "../sections/SupportMessageBody";
import SupportReplyBox from "../sections/SupportReplyBox";
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
  const [loading, setLoading] = useState(true);
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

  const applyStatus = async (next: "open" | "closed") => {
    try {
      await setThreadStatus(threadId, next);
      load();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  /** Mở lại thì làm luôn. KHÉP thì hỏi lại trước: khép rồi là mất ô phản hồi — 26/09/2026 lãnh đạo
   *  đơn vị bấm "Đánh dấu đã xong" vì tưởng là "đã nhận", rồi không trả lời được thông báo nữa. */
  const toggleStatus = () => {
    if (!thread) return;
    if (thread.status === "closed") { void applyStatus("open"); return; }
    const unitSilent = !messages.some((m) => m.side === "unit");
    Modal.confirm({
      title: "Khép thẻ này?",
      content: ctx?.side === "hq"
        ? `Khép thẻ thì đơn vị KHÔNG phản hồi thêm được trong thẻ này.${unitSilent ? " Đơn vị chưa phản hồi lần nào." : ""}`
        : "Khép thẻ thì KHÔNG phản hồi thêm được trong thẻ này, và đơn vị không tự mở lại được. "
          + "Còn điều gì cần trao đổi, vui lòng gửi phản hồi trước rồi mới khép.",
      okText: "Khép thẻ", cancelText: "Quay lại",
      onOk: () => applyStatus("closed"),
    });
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
  const isHq = ctx.side === "hq";
  const fromHq = thread.kind !== "request";
  // Tập đoàn khép / mở lại mọi thẻ. Đơn vị chỉ KHÉP được yêu cầu do chính mình gửi lên: thẻ Tập đoàn
  // gửi xuống thì đơn vị phản hồi kết quả ngay trong thẻ. Mở lại chỉ Tập đoàn — để đơn vị tự mở lại
  // là quay về một thẻ gánh nhiều việc. Server chặn đúng luật này (`assert_may_set_status`).
  const canToggle = ctx.can_write && (isHq || (!closed && !fromHq));

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2>{thread.subject}</h2>
          <p>
            <Tag color={KIND_COLOR[thread.kind]}>
              {KIND_LABEL[thread.kind]}
            </Tag>
            {isHq && <b style={{ marginRight: 10 }}>{thread.company}</b>}
            Mở lúc {stampVN(thread.created_at)}
            {closed && <Tag style={{ marginLeft: 8 }}>Đã đóng</Tag>}
          </p>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => nav("/ho-tro")}><ArrowLeftOutlined /> Hộp thư</button>
          {canToggle && (
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

      {ctx.can_write && (
        <SupportReplyBox threadId={threadId} closed={closed} isHq={isHq} fromHq={fromHq}
          onSent={load} onCompose={() => setComposing(true)} />
      )}

      {composing && (
        <SupportComposer ctx={ctx} onClose={() => setComposing(false)}
          onSent={(newId) => { setComposing(false); if (newId) nav(`/ho-tro/${newId}`); else nav("/ho-tro"); }} />
      )}
    </div>
  );
}
