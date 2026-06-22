import { ragMessages } from "../../../data/sample-data-panels";

/** Private RAG: hỏi đáp tài liệu nội bộ tiếng Việt (demo tĩnh — Sprint 2 nối LLM thật). */
export default function RagChat() {
  return (
    <div className="card" style={{ marginBottom: 18 }} id="sec-rag">
      <div className="card-head">
        <h3 className="title-demo">Private RAG · Hỏi đáp tài liệu nội bộ bằng tiếng Việt</h3>
        <span className="chip demo">Dữ liệu mẫu</span>
      </div>
      <div className="chatbox">
        {ragMessages.map((m, i) => (
          <div className={`msg ${m.role}`} key={i}>
            <div className="av">{m.role === "user" ? "HN" : "AI"}</div>
            <div className="bubble">
              {m.text}
              {m.cite && <div className="cite">{m.cite}</div>}
            </div>
          </div>
        ))}
      </div>
      <div className="chat-input">
        <input placeholder="Hỏi: 'Xu hướng dầu Brent ảnh hưởng giá RSS3 thế nào?' · 'Tìm báo cáo ANRPC tháng 4'..." />
        <button>Gửi ↵</button>
      </div>
    </div>
  );
}
