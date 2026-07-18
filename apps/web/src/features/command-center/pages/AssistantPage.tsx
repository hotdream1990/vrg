/* Trợ lý AI nội bộ — hỏi đáp số liệu thị trường/nội bộ + tư vấn giá sàn (tool-calling).
   Trả lời kèm bảng/biểu đồ (artifact) + trích nguồn. Gác cap `assistant`. */

import { RobotOutlined, SendOutlined } from "@ant-design/icons";
import { Button, Input, Spin, Tag, message as antdMessage } from "antd";
import { useEffect, useRef, useState } from "react";

import { type ChatArtifact, type ChatMessage, sendChat } from "../../../lib/assistant-client";
import AssistantArtifact from "./AssistantArtifact";

type UiMsg = { role: "user" | "assistant"; content: string; artifacts?: ChatArtifact[]; sources?: string[] };

const SUGGESTIONS = [
  "Giá sàn Tập đoàn hiện hành là bao nhiêu?",
  "Nên tăng hay giảm giá sàn lúc này? Vì sao?",
  "Diễn biến RSS3 trên SGX 30 ngày qua?",
  "Tồn kho thành phẩm mấy tuần gần đây thế nào?",
];

/** Render text đơn giản: xuống dòng + **đậm**. */
function renderText(text: string) {
  return text.split("\n").map((line, li) => (
    <div key={li} style={{ minHeight: line ? undefined : 8 }}>
      {line.split(/(\*\*[^*]+\*\*)/g).map((seg, si) =>
        seg.startsWith("**") && seg.endsWith("**")
          ? <b key={si}>{seg.slice(2, -2)}</b>
          : <span key={si}>{seg}</span>)}
    </div>
  ));
}

export default function AssistantPage() {
  const [msgs, setMsgs] = useState<UiMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, loading]);

  const ask = async (q: string) => {
    const question = q.trim();
    if (!question || loading) return;
    const next: UiMsg[] = [...msgs, { role: "user", content: question }];
    setMsgs(next);
    setInput("");
    setLoading(true);
    try {
      const history: ChatMessage[] = next.slice(-12).map((m) => ({ role: m.role, content: m.content }));
      const r = await sendChat(history);
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, artifacts: r.artifacts, sources: r.sources }]);
    } catch (e) {
      antdMessage.error((e as Error).message);
      setMsgs((m) => [...m, { role: "assistant", content: "Xin lỗi, có lỗi khi xử lý câu hỏi. Vui lòng thử lại." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 16, maxWidth: 1000, margin: "0 auto", display: "flex", flexDirection: "column", height: "calc(100vh - 96px)" }}>
      <div style={{ marginBottom: 8 }}>
        <h2 style={{ margin: 0 }}><RobotOutlined style={{ marginRight: 8, color: "#0a9e48" }} />Trợ lý AI</h2>
        <p style={{ opacity: 0.7, margin: "4px 0 0" }}>
          Hỏi đáp số liệu thị trường & nội bộ, tư vấn điều chỉnh giá sàn — trả lời kèm bảng/biểu đồ từ số liệu thật.
        </p>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "8px 4px" }}>
        {msgs.length === 0 && (
          <div style={{ opacity: 0.85, marginTop: 8 }}>
            <div style={{ marginBottom: 8, fontSize: 13 }}>Gợi ý câu hỏi:</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {SUGGESTIONS.map((s) => (
                <Tag key={s} color="green" style={{ cursor: "pointer", padding: "4px 10px", fontSize: 13 }}
                     onClick={() => ask(s)}>{s}</Tag>
              ))}
            </div>
          </div>
        )}

        {msgs.map((m, i) => (
          <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start", margin: "10px 0" }}>
            <div style={{
              maxWidth: m.role === "user" ? "78%" : "94%",
              background: m.role === "user" ? "#0a9e48" : "rgba(125,180,140,.14)",
              color: m.role === "user" ? "#fff" : "inherit",
              border: m.role === "user" ? "none" : "1px solid rgba(125,180,140,.35)",
              borderRadius: 12, padding: "10px 14px", fontSize: 14, lineHeight: 1.55,
            }}>
              {renderText(m.content)}
              {m.artifacts?.map((a, ai) => <AssistantArtifact key={ai} art={a} />)}
              {m.sources && m.sources.length > 0 && (
                <div style={{ marginTop: 8, fontSize: 11.5, opacity: 0.6 }}>
                  📎 Nguồn: {m.sources.join(" · ")}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && <div style={{ margin: "10px 0", opacity: 0.7 }}><Spin size="small" /> <span style={{ marginLeft: 8 }}>Trợ lý đang tra cứu số liệu…</span></div>}
        <div ref={endRef} />
      </div>

      <div style={{ display: "flex", gap: 8, paddingTop: 8, borderTop: "1px solid rgba(125,125,125,.15)" }}>
        <Input.TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={(e) => { if (!e.shiftKey) { e.preventDefault(); ask(input); } }}
          placeholder="Hỏi: 'Nên tăng giảm giá sàn không?' · 'Diễn biến SGX RSS3'…"
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={loading}
        />
        <Button type="primary" icon={<SendOutlined />} loading={loading} onClick={() => ask(input)}>Gửi</Button>
      </div>
    </div>
  );
}
