/* Trợ lý AI nội bộ — hỏi đáp số liệu thị trường/nội bộ + tư vấn giá sàn (tool-calling).
   Trả lời kèm bảng/biểu đồ (artifact) + trích nguồn. Gác cap `assistant`.
   Người dùng giới hạn Trợ lý bằng 2 công tắc: NGUỒN THAM CHIẾU (đi xa tới đâu trong kho số liệu)
   và MỨC TƯ VẤN (được phép khuyên tới đâu). Chi tiết từng gói kỹ năng nằm ở lớp nâng cao. */

import {
  InfoCircleOutlined, LockOutlined, PaperClipOutlined, RobotOutlined, SendOutlined,
  SettingOutlined, StopOutlined,
} from "@ant-design/icons";
import { Button, Input, Popover, Segmented, Spin, Tag, Tooltip, message as antdMessage } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  type AdviceLevel, type ChatArtifact, type ChatMessage, type SkillPack, fetchPacks, sendChat,
} from "../../../lib/assistant-client";
import AssistantArtifact from "./AssistantArtifact";

type UiMsg = { role: "user" | "assistant"; content: string; artifacts?: ChatArtifact[]; sources?: string[] };

/** Nguồn tham chiếu — "Trợ lý được đọc tới đâu". `custom` = người dùng tự bật/tắt từng gói. */
type Scope = "basic" | "extended" | "custom";

const STORAGE_KEY = "vrg.assistant.packs.off";
const SCOPE_KEY = "vrg.assistant.scope";
const ADVICE_KEY = "vrg.assistant.advice";
const MAX_SUGGESTIONS = 6;
const HISTORY_TURNS = 12;

/** Gói nền — khớp cờ `core` ở backend. Chỉ dùng khi CHƯA tải được danh sách gói (API lỗi),
 *  để nút "Cơ bản" vẫn thu hẹp đúng phạm vi thay vì rơi về "mở hết". */
const FALLBACK_BASIC_PACKS = ["market", "floor"];

const UNAVAILABLE_HINT = "Không khả dụng với tài khoản của bạn hoặc đã tắt trong Cấu hình hệ thống";

/** Gợi ý câu hỏi theo từng gói — chỉ hiện gợi ý của gói đang bật, hỏi đúng thứ Trợ lý tra được. */
const PACK_SUGGESTIONS: Record<string, string[]> = {
  market: [
    "Giá SMR20 trên MRB và SGX TSR20 hôm nay thế nào?",
    "Tỷ giá USD/VND mới nhất?",
  ],
  floor: [
    "Giá sàn Tập đoàn hiện hành là bao nhiêu?",
    "Nên tăng hay giảm giá sàn lúc này? Vì sao?",
  ],
  internal: [
    "Giá mủ nước 30 ngày qua diễn biến ra sao?",
    "Tồn kho thành phẩm mấy tuần gần đây?",
  ],
  unit: [
    "Tồn kho các đơn vị theo khu vực hiện thế nào?",
    "Đơn vị nào chưa nộp báo cáo tuần này?",
  ],
};

/** Dùng khi chưa lấy được danh sách gói (API lỗi) — màn chat vẫn phải dùng được bình thường. */
const FALLBACK_SUGGESTIONS = [
  "Giá sàn Tập đoàn hiện hành là bao nhiêu?",
  "Nên tăng hay giảm giá sàn lúc này? Vì sao?",
  "Diễn biến RSS3 trên SGX 30 ngày qua?",
  "Tồn kho thành phẩm mấy tuần gần đây thế nào?",
];

/* localStorage có trình duyệt chặn (chế độ riêng tư, chính sách máy trạm) → luôn bọc try/catch,
   hỏng chỗ ghi nhớ thì mất tiện nghi chứ không được làm sập màn chat. */
function readOffPacks(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    return Array.isArray(parsed) ? parsed.filter((k): k is string => typeof k === "string") : [];
  } catch {
    return [];
  }
}

function writeOffPacks(keys: string[]): void {
  writeStored(STORAGE_KEY, JSON.stringify(keys));
}

function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* không ghi nhớ được thì thôi — phiên này vẫn chạy đúng */
  }
}

/* ── Hai công tắc giới hạn Trợ lý ────────────────────────────────────────────────────────── */

const SCOPE_OPTIONS: { value: Scope; label: string; hint: string }[] = [
  { value: "basic", label: "Cơ bản",
    hint: "Chỉ nhóm nền: thị trường thế giới và giá sàn." },
  { value: "extended", label: "Mở rộng",
    hint: "Thêm số liệu nội bộ Tập đoàn và số liệu đơn vị thành viên." },
];

const CUSTOM_SCOPE_OPTION: { value: Scope; label: string; hint: string } = {
  value: "custom", label: "Tuỳ chỉnh",
  hint: "Bạn đang tự bật/tắt từng nhóm dữ liệu ở phần Nâng cao.",
};

const ADVICE_OPTIONS: { value: AdviceLevel; label: string; hint: string; note: string }[] = [
  { value: "data", label: "Chỉ tra số",
    hint: "Trợ lý không đưa khuyến nghị nâng/giữ/hạ, chỉ trả số liệu.",
    note: "Trợ lý chỉ trả số liệu và diễn giải số liệu, không đưa khuyến nghị nâng/giữ/hạ giá sàn." },
  { value: "model", label: "Theo mô hình",
    hint: "Trợ lý đưa đúng đề xuất của mô hình, không tự điều chỉnh.",
    note: "Trợ lý nêu đúng mức mô hình gợi ý, không tự điều chỉnh theo bối cảnh. Mọi khuyến nghị chỉ để tham khảo, không ghi vào biểu giá sàn." },
  { value: "adjusted", label: "Có điều chỉnh",
    hint: "Trợ lý được lệch khỏi mức mô hình dựa trên bối cảnh, phải giải trình.",
    note: "Trợ lý có thể đề xuất khác mức mô hình và phải nêu rõ lý do. Mọi khuyến nghị chỉ để tham khảo, không ghi vào biểu giá sàn." },
];

const DEFAULT_SCOPE: Scope = "extended";
const DEFAULT_ADVICE: AdviceLevel = "model";

function readScope(): Scope {
  const raw = readStored(SCOPE_KEY);
  return raw === "basic" || raw === "extended" || raw === "custom" ? raw : DEFAULT_SCOPE;
}

function readAdvice(): AdviceLevel {
  const raw = readStored(ADVICE_KEY);
  return ADVICE_OPTIONS.some((o) => o.value === raw) ? (raw as AdviceLevel) : DEFAULT_ADVICE;
}

/** Danh sách gói gửi lên backend, suy từ công tắc "Nguồn tham chiếu".
 *  `off` = các gói người dùng đã tắt tay (chỉ có nghĩa ở chế độ Tuỳ chỉnh). */
function packsForScope(scope: Scope, packs: SkillPack[], off: string[]): string[] {
  if (packs.length === 0) return scope === "basic" ? FALLBACK_BASIC_PACKS : [];
  const active = packs.filter((p) => p.active);
  if (scope === "basic") return active.filter((p) => p.core).map((p) => p.key);
  if (scope === "extended") return active.map((p) => p.key);
  // Tuỳ chỉnh: gói nền luôn bật kể cả khi bản ghi nhớ cũ lỡ tắt nó.
  return active.filter((p) => p.core || !off.includes(p.key)).map((p) => p.key);
}

/** Gom gợi ý theo VÒNG TRÒN mỗi gói một câu: cắt thẳng từ đầu danh sách sẽ khiến gói xếp sau
 *  (vd `unit`) không bao giờ có gợi ý nào lọt vào ngưỡng tối đa. */
function buildSuggestions(packs: SkillPack[], selected: string[]): string[] {
  const pools = packs
    .filter((p) => selected.includes(p.key))
    .map((p) => PACK_SUGGESTIONS[p.key] ?? [])
    .filter((pool) => pool.length > 0);
  if (pools.length === 0) return FALLBACK_SUGGESTIONS.slice(0, MAX_SUGGESTIONS);

  const out: string[] = [];
  for (let round = 0; out.length < MAX_SUGGESTIONS; round += 1) {
    const before = out.length;
    for (const pool of pools) {
      if (out.length >= MAX_SUGGESTIONS) break;
      if (pool[round]) out.push(pool[round]);
    }
    if (out.length === before) break; // mọi gói đã cạn câu gợi ý
  }
  return out;
}

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

/* CheckableTag của antd v6 để chip CHƯA chọn nền + viền trong suốt → nhìn như chữ trơ, không ra
   hình viên chip. Vẽ lại viền cho 2 trạng thái tắt để cả hàng đọc được là "các nút bật/tắt". */
const CHIP_BASE: React.CSSProperties = { padding: "3px 10px", fontSize: 13, borderRadius: 8 };
const CHIP_OFF: React.CSSProperties = { ...CHIP_BASE, border: "1px solid rgba(125,180,140,.45)", background: "rgba(125,180,140,.10)" };
const CHIP_LOCKED: React.CSSProperties = { ...CHIP_BASE, cursor: "default" };
const CHIP_UNAVAILABLE: React.CSSProperties = { ...CHIP_BASE, border: "1px dashed rgba(140,140,140,.45)", opacity: 0.6 };

/** Hàng chip chọn gói kỹ năng (lớp NÂNG CAO, trong Popover).
 *  3 trạng thái: nền (khoá) · bật/tắt được · không khả dụng (mờ). */
function SkillPackChips({ packs, selected, onToggle }: {
  packs: SkillPack[];
  selected: string[];
  onToggle: (pack: SkillPack, checked: boolean) => void;
}) {
  if (packs.length === 0) return null; // API lỗi hoặc chưa tải xong → ẩn hàng chip, không chặn chat

  return (
    <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
      {packs.map((pack) => {
        const checked = selected.includes(pack.key);
        const base = `${pack.desc} (${pack.tools} công cụ)`;
        if (pack.core) {
          return (
            <Tooltip key={pack.key} title={`${base} · Nhóm nền — luôn bật.`}>
              <Tag.CheckableTag
                checked
                icon={<LockOutlined />}
                onChange={() => { /* gói nền: khoá, bấm không đổi trạng thái */ }}
                style={CHIP_LOCKED}
              >
                {pack.label}
              </Tag.CheckableTag>
            </Tooltip>
          );
        }
        if (!pack.active) {
          return (
            <Tooltip key={pack.key} title={`${base} · ${UNAVAILABLE_HINT}.`}>
              <Tag.CheckableTag
                checked={false}
                disabled
                icon={<StopOutlined />}
                style={CHIP_UNAVAILABLE}
              >
                {pack.label}
              </Tag.CheckableTag>
            </Tooltip>
          );
        }
        return (
          <Tooltip key={pack.key} title={base}>
            <Tag.CheckableTag
              checked={checked}
              onChange={(next) => onToggle(pack, next)}
              style={checked ? CHIP_BASE : CHIP_OFF}
            >
              {pack.label}
            </Tag.CheckableTag>
          </Tooltip>
        );
      })}
    </div>
  );
}

const SWITCH_LABEL: React.CSSProperties = { fontSize: 12.5, opacity: 0.7 };

/** Nhãn Segmented kèm Tooltip giải thích — người dùng hiểu ngay "cho AI đi xa tới đâu". */
function tipOptions<T extends string>(opts: { value: T; label: string; hint: string }[]) {
  return opts.map((o) => ({
    value: o.value,
    label: <Tooltip title={o.hint}><span>{o.label}</span></Tooltip>,
  }));
}

/** Hai công tắc + lối vào lớp nâng cao (chi tiết từng gói kỹ năng). */
function AssistantControls({ packs, scope, advice, selected, onScope, onAdvice, onToggle }: {
  packs: SkillPack[];
  scope: Scope;
  advice: AdviceLevel;
  selected: string[];
  onScope: (next: Scope) => void;
  onAdvice: (next: AdviceLevel) => void;
  onToggle: (pack: SkillPack, checked: boolean) => void;
}) {
  // "Tuỳ chỉnh" chỉ hiện khi người dùng đã tự chỉnh chip — công tắc thường chỉ có 2 lựa chọn.
  const scopeOptions = useMemo(
    () => tipOptions(scope === "custom" ? [...SCOPE_OPTIONS, CUSTOM_SCOPE_OPTION] : SCOPE_OPTIONS),
    [scope],
  );
  const adviceOptions = useMemo(() => tipOptions(ADVICE_OPTIONS), []);
  const note = ADVICE_OPTIONS.find((o) => o.value === advice)?.note ?? "";

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: "8px 14px" }}>
        <span style={SWITCH_LABEL}>Nguồn tham chiếu:</span>
        <Segmented size="small" value={scope} options={scopeOptions}
                   onChange={(v) => onScope(v as Scope)} />
        <span style={SWITCH_LABEL}>Mức tư vấn:</span>
        <Segmented size="small" value={advice} options={adviceOptions}
                   onChange={(v) => onAdvice(v as AdviceLevel)} />
        {packs.length > 0 && (
          <Popover
            trigger="click"
            placement="bottomLeft"
            title="Chi tiết nhóm dữ liệu"
            content={(
              <div style={{ maxWidth: 460 }}>
                <div style={{ ...SWITCH_LABEL, marginBottom: 8 }}>
                  Bật/tắt từng nhóm Trợ lý được phép tra cứu. Nhóm nền luôn bật; nhóm mờ là không
                  khả dụng với tài khoản của bạn.
                </div>
                <SkillPackChips packs={packs} selected={selected} onToggle={onToggle} />
              </div>
            )}
          >
            <Button type="link" size="small" icon={<SettingOutlined />} style={{ paddingInline: 0 }}>
              Nâng cao
            </Button>
          </Popover>
        )}
      </div>
      <div style={{ fontSize: 12, opacity: 0.65, marginTop: 6 }}>
        <InfoCircleOutlined style={{ marginRight: 6 }} />{note}
      </div>
    </div>
  );
}

export default function AssistantPage() {
  const [msgs, setMsgs] = useState<UiMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [packs, setPacks] = useState<SkillPack[]>([]);
  const [scope, setScope] = useState<Scope>(readScope);
  const [advice, setAdvice] = useState<AdviceLevel>(readAdvice);
  const [offPacks, setOffPacks] = useState<string[]>(readOffPacks);
  const endRef = useRef<HTMLDivElement>(null);
  // Mã phiên chat: gom các lượt của cùng một lần trò chuyện vào một dòng trong "Lịch sử hỏi đáp".
  // `randomUUID` không có trên vài trình duyệt cũ/ngữ cảnh không bảo mật → có đường lui.
  const sessionId = useRef<string>(
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `s-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
  );

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, loading]);

  useEffect(() => {
    let cancelled = false;
    fetchPacks()
      .then((r) => { if (!cancelled) setPacks(r.packs ?? []); })
      .catch(() => { /* không lấy được danh sách gói → ẩn lớp nâng cao, chat vẫn chạy bình thường */ });
    return () => { cancelled = true; };
  }, []);

  const selected = useMemo(() => packsForScope(scope, packs, offPacks), [scope, packs, offPacks]);
  const suggestions = useMemo(() => buildSuggestions(packs, selected), [packs, selected]);

  const pickScope = (next: Scope) => { setScope(next); writeStored(SCOPE_KEY, next); };
  const pickAdvice = (next: AdviceLevel) => { setAdvice(next); writeStored(ADVICE_KEY, next); };

  const toggle = (pack: SkillPack, checked: boolean) => {
    if (pack.core || !pack.active) return; // khoá: gói nền và gói không khả dụng
    // Ghi nhớ theo danh sách gói BỊ TẮT (không phải gói đang bật): gói mới backend thêm sau này
    // sẽ mặc định bật, thay vì bị tắt âm thầm chỉ vì chưa có trong bản ghi nhớ cũ.
    // Rời Cơ bản/Mở rộng thì lấy chính lựa chọn đang hiển thị làm điểm xuất phát cho Tuỳ chỉnh.
    const base = scope === "custom"
      ? offPacks
      : packs.filter((p) => p.active && !p.core && !selected.includes(p.key)).map((p) => p.key);
    const rest = base.filter((k) => k !== pack.key);
    const next = checked ? rest : [...rest, pack.key];
    setOffPacks(next);
    writeOffPacks(next);
    pickScope("custom");
  };

  const ask = async (q: string) => {
    const question = q.trim();
    if (!question || loading) return;
    const next: UiMsg[] = [...msgs, { role: "user", content: question }];
    setMsgs(next);
    setInput("");
    setLoading(true);
    try {
      const history: ChatMessage[] = next.slice(-HISTORY_TURNS).map((m) => ({ role: m.role, content: m.content }));
      const r = await sendChat(history, selected, advice, sessionId.current);
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, artifacts: r.artifacts, sources: r.sources }]);
    } catch (e) {
      antdMessage.error((e as Error).message);
      setMsgs((m) => [...m, { role: "assistant", content: "Xin lỗi, có lỗi khi xử lý câu hỏi. Vui lòng thử lại." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 16, maxWidth: 1000, margin: "0 auto", display: "flex", flexDirection: "column", height: "calc(100vh - 150px)" }}>
      <div style={{ marginBottom: 8 }}>
        <h2 style={{ margin: 0 }}><RobotOutlined style={{ marginRight: 8, color: "#0a9e48" }} />Trợ lý AI</h2>
        <p style={{ opacity: 0.7, margin: "4px 0 0" }}>
          Hỏi đáp số liệu thị trường & nội bộ, tư vấn điều chỉnh giá sàn — trả lời kèm bảng/biểu đồ từ số liệu thật.
        </p>
        <AssistantControls
          packs={packs}
          scope={scope}
          advice={advice}
          selected={selected}
          onScope={pickScope}
          onAdvice={pickAdvice}
          onToggle={toggle}
        />
      </div>

      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "8px 4px" }}>
        {msgs.length === 0 && (
          <div style={{ opacity: 0.85, marginTop: 8 }}>
            <div style={{ marginBottom: 8, fontSize: 13 }}>Gợi ý câu hỏi:</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {suggestions.map((s) => (
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
                  <PaperClipOutlined style={{ marginRight: 4 }} />Nguồn: {m.sources.join(" · ")}
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
