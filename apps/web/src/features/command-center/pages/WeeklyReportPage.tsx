import { CheckCircleOutlined, FileDoneOutlined, RobotOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  type WeeklyNarrative,
  type WeeklyReport,
  type WeeklyReportSummary,
  aiAssistAllWeekly,
  aiAssistWeekly,
  deleteWeeklyReport,
  generateWeeklyPdf,
  getWeeklyReport,
  listWeeklyReports,
  resolveWeek,
  saveWeeklyReport,
} from "../../../lib/weekly-report-client";
import { useAuth } from "../../auth/AuthContext";
import DateInput from "../sections/DateInput";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import WeeklyTables from "./components/WeeklyTables";
import "../../bulletin/bulletin.css";

const todayISO = () => new Date().toISOString().slice(0, 10);

/** Textarea sửa list đoạn/gạch đầu dòng (mỗi dòng = 1 ý; ">" đầu dòng = gạch phụ). */
function ListField({ label, hint, items, readOnly, busy, onChange, onAI }: {
  label: string; hint?: string; items: string[]; readOnly: boolean; busy?: boolean;
  onChange: (v: string[]) => void; onAI?: () => void;
}) {
  return (
    <div className="wk-field">
      <div className="wk-field-head">
        <label>{label}</label>
        {onAI && !readOnly && (
          <button className="btn btn-sm" onClick={onAI} disabled={busy}>
            {busy ? <span className="spinner" /> : <RobotOutlined />} AI hỗ trợ
          </button>
        )}
      </div>
      {hint && <div className="wk-hint">{hint}</div>}
      <textarea className="blt-date-input" style={{ width: "100%", minHeight: 84, resize: "vertical" }}
        value={items.join("\n")} readOnly={readOnly}
        placeholder="Mỗi dòng một ý…"
        onChange={(e) => onChange(e.target.value.split("\n"))} />
    </div>
  );
}

export default function WeeklyReportPage() {
  const { canEdit } = useAuth();
  const [list, setList] = useState<WeeklyReportSummary[]>([]);
  const [draft, setDraft] = useState<WeeklyReport | null>(null);
  const [pickDate, setPickDate] = useState(todayISO());
  const [save, setSave] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [savedAt, setSavedAt] = useState("");
  const [aiBusy, setAiBusy] = useState("");
  const [aiAll, setAiAll] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const lastSaved = useRef("");
  const timer = useRef<number | null>(null);

  const loadList = useCallback(() => {
    listWeeklyReports().then(setList).catch((e) => setErr(e.message));
  }, []);
  useEffect(() => { loadList(); }, [loadList]);

  // Auto-save narrative (debounce 0.9s)
  useEffect(() => {
    if (!draft || !canEdit) return;
    const json = JSON.stringify(draft.narrative);
    if (json === lastSaved.current) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      setSave("saving"); setErr("");
      saveWeeklyReport(draft.week_key, draft.narrative).then((r) => {
        lastSaved.current = JSON.stringify(r.narrative);
        setDraft((d) => (d && d.week_key === r.week_key ? { ...d, ...pickTables(r) } : d));
        setSave("saved"); setSavedAt(new Date().toLocaleTimeString("vi-VN")); loadList();
      }).catch((e) => { setSave("error"); setErr(e.message); });
    }, 900);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [draft, canEdit, loadList]);

  const open = async (weekKey: string) => {
    setErr(""); setInfo("");
    try {
      const r = await getWeeklyReport(weekKey);
      lastSaved.current = JSON.stringify(r.narrative);
      setSave("idle"); setSavedAt(""); setDraft(r);
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
  };
  const openByDate = async () => {
    try { const { week_key } = await resolveWeek(pickDate); await open(week_key); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
  };

  const setNar = (patch: Partial<WeeklyNarrative>) =>
    setDraft((d) => d && { ...d, narrative: { ...d.narrative, ...patch } });
  const setLatex = (patch: { latex_prev?: string; latex_curr?: string; latex_change?: string }) =>
    setDraft((d) => d && { ...d, ...patch, narrative: { ...d.narrative, ...patch } });
  const setMacroBullets = (i: number, bullets: string[]) =>
    setDraft((d) => {
      if (!d) return d;
      const macro = d.narrative.macro.map((m, idx) => (idx === i ? { ...m, bullets } : m));
      return { ...d, narrative: { ...d.narrative, macro } };
    });

  const ai = async (section: string, apply: (paras: string[]) => void) => {
    if (!draft) return;
    setAiBusy(section); setErr("");
    try { const r = await aiAssistWeekly(draft.week_key, section); apply(r.paragraphs); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi AI"); }
    finally { setAiBusy(""); }
  };

  const hasNarrative = (n: WeeklyNarrative) =>
    [n.summary_prev, n.movement, n.exchange_notes, n.physical_notes, n.latex_notes, n.forecast,
      n.conclusion].some((a) => a.some((s) => s.trim())) || n.macro.some((m) => m.bullets.some((s) => s.trim()));

  const aiAllRun = async () => {
    if (!draft) return;
    if (hasNarrative(draft.narrative) &&
      !confirm("Sinh lại TOÀN BỘ nội dung bằng AI (nhất quán các phần)? Nội dung đang có ở các phần viết sẽ bị thay.")) return;
    setAiAll(true); setErr("");
    try { const r = await aiAssistAllWeekly(draft.week_key); setNar({ ...r.sections }); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi AI"); }
    finally { setAiAll(false); }
  };

  const exportPdf = async () => {
    if (!draft) return;
    setBusy(true); setErr("");
    try {
      // Lưu trước để PDF dùng nội dung mới nhất
      await saveWeeklyReport(draft.week_key, draft.narrative);
      await generateWeeklyPdf(draft.week_key, `Bao-cao-tuan-${draft.week_no}-${draft.year}.pdf`);
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi xuất PDF"); }
    finally { setBusy(false); }
  };

  const remove = async () => {
    if (!draft || !confirm(`Xoá báo cáo tuần ${draft.week_no}/${draft.year}?`)) return;
    setBusy(true);
    try { await deleteWeeklyReport(draft.week_key); setDraft(null); loadList(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi xoá"); }
    finally { setBusy(false); }
  };

  const saveText = save === "saving" ? "Đang lưu…" : save === "saved" ? `Đã lưu ${savedAt}`
    : save === "error" ? "Lỗi lưu" : "Tự lưu khi nhập";

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><FileDoneOutlined style={{ marginRight: 8 }} />Báo cáo phân tích thị trường tuần</h2>
          <p>Chọn tuần → bảng số liệu tự tính (TB tuần), các phần viết có AI hỗ trợ + sửa tay, xuất PDF theo mẫu.</p>
        </div>
        {canEdit && (
          <div className="actions" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label className="blt-date-label" style={{ margin: 0, whiteSpace: "nowrap" }}>Tuần chứa ngày:
              <DateInput value={pickDate} noFuture style={{ width: 140 }}
                onChange={(v) => setPickDate(v || todayISO())} />
            </label>
            <button className="btn btn-primary" onClick={openByDate}>Mở / Tạo tuần</button>
          </div>
        )}
      </div>

      <ReadOnlyNotice />
      {err && <div className="blt-error">{err}</div>}
      {info && <div className="blt-info">{info}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head"><h3>Báo cáo đã lưu</h3></div>
        {list.length === 0 ? (
          <div className="scan-empty">Chưa có báo cáo — chọn ngày rồi bấm "Mở / Tạo tuần".</div>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {list.map((s) => (
              <button key={s.week_key} className={`btn${draft?.week_key === s.week_key ? " btn-primary" : ""}`}
                onClick={() => open(s.week_key)}>{s.label}</button>
            ))}
          </div>
        )}
      </div>

      {draft && (
        <>
          <div className="card blt-section" style={{ marginBottom: 16 }}>
            <div className="blt-section-header">
              <h3>Tuần {draft.week_no}/{draft.year} ({draft.date_range})</h3>
              <div className="blt-section-meta" style={{ alignItems: "center" }}>
                {canEdit && (
                  <span className="db-badge" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    {save === "saving" ? <span className="spinner" /> : <CheckCircleOutlined />} {saveText}
                  </span>
                )}
                {canEdit && (
                  <button className="btn btn-primary" onClick={aiAllRun} disabled={aiAll || busy}>
                    {aiAll ? <><span className="spinner" /> Đang tạo…</> : <><RobotOutlined /> AI hỗ trợ toàn bộ</>}
                  </button>
                )}
                <button className="btn" onClick={exportPdf} disabled={busy || aiAll}>
                  {busy ? <><span className="spinner" /> Đang xuất…</> : "Xuất PDF"}
                </button>
                {canEdit && <button className="btn" onClick={remove} disabled={busy}>Xoá</button>}
              </div>
            </div>
          </div>

          <div className="card blt-section blt-editable" style={{ marginBottom: 16 }}>
            <ListField label={`I. Tóm tắt tuần ${draft.prev_week_no}/${draft.prev_year}`} items={draft.narrative.summary_prev}
              readOnly={!canEdit} busy={aiBusy === "summary_prev"} onChange={(v) => setNar({ summary_prev: v })}
              onAI={() => ai("summary_prev", (p) => setNar({ summary_prev: p }))} />
            <ListField label={`II. Diễn biến tuần ${draft.week_no}/${draft.year}`} items={draft.narrative.movement}
              readOnly={!canEdit} busy={aiBusy === "movement"} onChange={(v) => setNar({ movement: v })}
              onAI={() => ai("movement", (p) => setNar({ movement: p }))} />
          </div>

          <div className="card blt-section blt-editable" style={{ marginBottom: 16 }}>
            <div className="blt-section-header"><h3>III. Diễn biến giá</h3></div>
            <WeeklyTables report={draft} readOnly={!canEdit} onLatex={setLatex} />
            <ListField label="Nhận định III.1 (sàn quốc tế)" hint="Gạch phụ (Cao/Thấp nhất tuần): mở đầu dòng bằng >"
              items={draft.narrative.exchange_notes} readOnly={!canEdit} busy={aiBusy === "exchange_notes"}
              onChange={(v) => setNar({ exchange_notes: v })}
              onAI={() => ai("exchange_notes", (p) => setNar({ exchange_notes: p }))} />
            <ListField label="Nhận định III.2 (giao ngay)" items={draft.narrative.physical_notes}
              readOnly={!canEdit} busy={aiBusy === "physical_notes"} onChange={(v) => setNar({ physical_notes: v })}
              onAI={() => ai("physical_notes", (p) => setNar({ physical_notes: p }))} />
            <ListField label="Nhận định III.3 (mủ nước)" items={draft.narrative.latex_notes}
              readOnly={!canEdit} busy={aiBusy === "latex_notes"} onChange={(v) => setNar({ latex_notes: v })}
              onAI={() => ai("latex_notes", (p) => setNar({ latex_notes: p }))} />
          </div>

          <div className="card blt-section blt-editable" style={{ marginBottom: 16 }}>
            <div className="blt-section-header"><h3>IV. Các yếu tố vĩ mô</h3></div>
            {draft.narrative.macro.map((m, i) => (
              <ListField key={i} label={m.title} items={m.bullets} readOnly={!canEdit}
                busy={aiBusy === `macro:${i}`} onChange={(v) => setMacroBullets(i, v)}
                onAI={() => ai(`macro:${i}`, (p) => setMacroBullets(i, p))} />
            ))}
          </div>

          <div className="card blt-section blt-editable" style={{ marginBottom: 16 }}>
            <ListField label={`V. Dự báo xu hướng tuần ${draft.next_week_no}/${draft.next_year}`}
              hint="Gạch đầu dòng (Xu hướng chủ đạo / Tiêu điểm quan sát): mở đầu bằng -"
              items={draft.narrative.forecast} readOnly={!canEdit} busy={aiBusy === "forecast"}
              onChange={(v) => setNar({ forecast: v })} onAI={() => ai("forecast", (p) => setNar({ forecast: p }))} />
            <ListField label="VI. Kết luận và khuyến nghị" items={draft.narrative.conclusion}
              readOnly={!canEdit} busy={aiBusy === "conclusion"} onChange={(v) => setNar({ conclusion: v })}
              onAI={() => ai("conclusion", (p) => setNar({ conclusion: p }))} />
          </div>
        </>
      )}
    </div>
  );
}

/** Lấy phần bảng (auto) từ report trả về sau khi lưu, giữ nguyên narrative đang gõ. */
function pickTables(r: WeeklyReport) {
  return {
    exchange_rows: r.exchange_rows, physical_rows: r.physical_rows,
    latex_prev: r.latex_prev, latex_curr: r.latex_curr, latex_change: r.latex_change,
  };
}
