import { FileDoneOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useRef, useState } from "react";

import { todayISO } from "../../../lib/date";
import {
  type WeeklyNarrative,
  type WeeklyReport,
  type WeeklyReportSummary,
  aiAssistAllWeekly,
  aiAssistWeekly,
  deleteWeeklyReport,
  generateWeeklyPdf,
  listWeeklyReports,
  resolveWeek,
  weeklyPdfName,
} from "../../../lib/weekly-report-client";
import {
  type WeeklySource,
  type WeeklySourceMeta,
  getWeeklySourceMeta,
  listWeeklySources,
} from "../../../lib/weekly-sources-client";
import { useAuth } from "../../auth/AuthContext";
import DateInput from "../sections/DateInput";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import { type WeeklyEditor, WeeklyEditorContext } from "./components/WeeklyEditorContext";
import WeeklyCheckBanner from "./components/WeeklyCheckBanner";
import WeeklyHeaderBar from "./components/WeeklyHeaderBar";
import WeeklyInputsPanel from "./components/WeeklyInputsPanel";
import WeeklySavedList from "./components/WeeklySavedList";
import WeeklyWritingSections from "./components/WeeklyWritingSections";
import { useWeeklyCheck } from "./components/useWeeklyCheck";
import { useWeeklyDraft } from "./components/useWeeklyDraft";
import "../../bulletin/bulletin.css";

const EMPTY_META: WeeklySourceMeta = { categories: [], modes: [], sections: [] };
const msg = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback);

const hasNarrative = (n: WeeklyNarrative) =>
  [n.summary_prev, n.movement, n.exchange_notes, n.physical_notes, n.latex_notes, n.forecast, n.conclusion]
    .some((a) => a.some((s) => s.trim())) || n.macro.some((m) => m.bullets.some((s) => s.trim()));

export default function WeeklyReportPage() {
  const { canEditCap } = useAuth();
  const canEdit = canEditCap("bulletin_weekly"); // mức Xem → vẫn xem, xuất PDF, tải đính kèm, mở nguồn
  const [list, setList] = useState<WeeklyReportSummary[]>([]);
  const [pickDate, setPickDate] = useState(todayISO());
  const [sources, setSources] = useState<WeeklySource[]>([]);
  const [meta, setMeta] = useState<WeeklySourceMeta>(EMPTY_META);
  const [sourcesError, setSourcesError] = useState("");
  const [aiBusy, setAiBusy] = useState("");
  const [aiAll, setAiAll] = useState(false);
  const [aiWarn, setAiWarn] = useState<Record<string, string[]>>({});
  const [aiAbs, setAiAbs] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const loadList = useCallback(() => {
    listWeeklyReports().then(setList).catch((e) => setErr(msg(e, "Lỗi")));
  }, []);
  const reloadSources = useCallback(async () => {
    try { setSources(await listWeeklySources()); setSourcesError(""); }
    catch (e) { setSourcesError(msg(e, "Không tải được danh mục nguồn")); }
  }, []);
  useEffect(() => {
    loadList();
    reloadSources();
    getWeeklySourceMeta().then(setMeta).catch(() => undefined); // thiếu meta → nhãn hiện bằng mã
  }, [loadList, reloadSources]);

  const listRef = useRef(list);
  listRef.current = list;
  // Chỉ nạp lại danh sách khi lượt lưu vừa TẠO báo cáo mới hoặc đổi kỳ (nhãn đổi) — không phải mỗi lần gõ.
  const onSaved = useCallback((r: WeeklyReport) => {
    const known = listRef.current.some((s) => s.week_key === r.week_key && (s.span_weeks ?? 1) === r.span_weeks);
    if (!known) loadList();
  }, [loadList]);
  const d = useWeeklyDraft(canEdit, onSaved);
  const { draft, setNar, setMacro } = d;
  const chk = useWeeklyCheck();
  const aiRunning = !!aiBusy || aiAll;

  const openWeek = async (weekKey: string) => {
    setErr(""); setAiWarn({}); setAiAbs({}); chk.reset();
    try { await d.open(weekKey); } catch (e) { setErr(msg(e, "Lỗi")); }
  };
  const openByDate = async () => {
    try { const { week_key } = await resolveWeek(pickDate); await openWeek(week_key); }
    catch (e) { setErr(msg(e, "Lỗi")); }
  };

  const setWarnFor = (key: string, warnings?: string[], abs?: string[]) => {
    setAiWarn((w) => ({ ...w, [key]: warnings ?? [] }));
    setAiAbs((w) => ({ ...w, [key]: abs ?? [] }));
  };

  // Kết quả AI chỉ áp vào ĐÚNG tuần đã gửi yêu cầu (người dùng có thể đã mở tuần khác).
  const runAi = async (key: string) => {
    if (!draft || aiRunning) return;
    const wk = draft.week_key;
    setAiBusy(key); setErr("");
    try {
      await d.flush(); // AI đọc bản đã lưu (số tuần gộp, tiêu đề IV, tóm tắt đính kèm mới nhất)
      const r = await aiAssistWeekly(wk, key);
      if (d.currentWeek() !== wk) return;
      if (key.startsWith("macro:")) setMacro(Number(key.slice(6)), { bullets: r.paragraphs }, wk);
      else setNar({ [key]: r.paragraphs } as Partial<WeeklyNarrative>, wk);
      setWarnFor(key, r.warnings, r.absolute_words); chk.clearKey(key); // chữ mới → kết quả soát cũ hết hiệu lực
    } catch (e) { setErr(msg(e, "Lỗi AI")); }
    finally { setAiBusy(""); }
  };

  const runAiAll = async () => {
    if (!draft || aiRunning) return;
    if (hasNarrative(draft.narrative) &&
      !confirm("Sinh lại TOÀN BỘ nội dung bằng AI (nhất quán các phần)? Nội dung đang có ở các phần viết sẽ bị thay.")) return;
    const wk = draft.week_key;
    setAiAll(true); setErr("");
    try {
      await d.flush();
      const r = await aiAssistAllWeekly(wk);
      if (d.currentWeek() !== wk) return;
      setNar({ ...r.sections }, wk);
      setAiWarn(r.warnings ?? {}); setAiAbs(r.absolute_words ?? {}); chk.reset();
    } catch (e) { setErr(msg(e, "Lỗi AI")); }
    finally { setAiAll(false); }
  };

  // Soát chữ ĐÃ LƯU với bảng số hiện tại → cảnh báo vào đúng ô. Người chỉ xem: soát bản đã lưu.
  const runCheck = async () => {
    if (!draft) return;
    const wk = draft.week_key;
    setErr("");
    try { await d.flush(); await chk.run(wk, () => d.currentWeek() === wk); }
    catch (e) { setErr(msg(e, "Lỗi soát số liệu")); }
  };

  const exportPdf = async () => {
    if (!draft) return;
    const wk = draft.week_key;
    setBusy(true); setErr("");
    try {
      // Người chỉ xem không lưu được (máy chủ từ chối) → xuất thẳng bản đã lưu.
      const saved = canEdit ? await d.flush() : draft;
      if (!(await chk.confirmExport(wk, () => d.currentWeek() === wk))) return;
      await generateWeeklyPdf(wk, weeklyPdfName(saved ?? draft));
    } catch (e) { setErr(msg(e, "Lỗi xuất PDF")); }
    finally { setBusy(false); }
  };

  const remove = async () => {
    if (!draft || !confirm(`Xoá báo cáo ${draft.title_label || `tuần ${draft.week_no}/${draft.year}`}? `
      + "Tài liệu đính kèm của kỳ này cũng bị xoá.")) return;
    setBusy(true);
    try {
      await d.cancel(); // bỏ lượt tự lưu đang hẹn giờ — nếu không, PUT sau DELETE tạo lại báo cáo
      await deleteWeeklyReport(draft.week_key); d.close(); loadList();
    } catch (e) { d.resume(); setErr(msg(e, "Lỗi xoá")); }
    finally { setBusy(false); }
  };

  const changeSpan = (n: number) => { d.setSpan(n); setAiWarn({}); setAiAbs({}); chk.reset(); };

  const editor: WeeklyEditor = {
    readOnly: !canEdit, sources, aiBusy, aiAll, locked: aiAll || busy, aiWarn, aiAbs,
    checkWarn: chk.result?.warnings ?? {},
    runAi: (k) => { void runAi(k); },
    clearWarn: (k) => { setWarnFor(k, [], []); chk.clearKey(k); },
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><FileDoneOutlined style={{ marginRight: 8 }} />Báo cáo phân tích thị trường tuần</h2>
          <p>Chọn tuần (gộp 1–3 tuần) → bảng số liệu tự tính, các phần viết có AI hỗ trợ + sửa tay, xuất PDF theo mẫu.</p>
        </div>
        {canEdit && (
          <div className="actions" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label className="blt-date-label" style={{ margin: 0, whiteSpace: "nowrap" }}>Tuần chứa ngày:
              <DateInput value={pickDate} noFuture style={{ width: 140 }}
                onChange={(v) => setPickDate(v || todayISO())} />
            </label>
            <button className="btn btn-primary" onClick={openByDate} disabled={aiRunning}>Mở / Tạo tuần</button>
          </div>
        )}
      </div>

      <ReadOnlyNotice cap="bulletin_weekly" />
      {err && <div className="blt-error">{err}</div>}
      {d.saveError && <div className="blt-error">Chưa lưu được: {d.saveError}</div>}

      <WeeklySavedList list={list} activeKey={draft?.week_key ?? null} canEdit={canEdit} disabled={aiRunning}
        onOpen={openWeek} />

      {draft && (
        <WeeklyEditorContext.Provider value={editor}>
          <WeeklyHeaderBar report={draft} canEdit={canEdit} save={d.save} savedAt={d.savedAt} aiAll={aiAll}
            aiOne={!!aiBusy} busy={busy} checking={chk.checking} onSpan={changeSpan} onAiAll={runAiAll}
            onCheck={runCheck} onPdf={exportPdf} onDelete={remove} />
          <WeeklyCheckBanner result={chk.result} onClose={chk.reset} />
          <WeeklyInputsPanel report={draft} canEdit={canEdit} sources={sources} meta={meta}
            sourcesError={sourcesError} reloadSources={reloadSources} />
          <WeeklyWritingSections report={draft} setNar={setNar} setMacro={setMacro} />
        </WeeklyEditorContext.Provider>
      )}
    </div>
  );
}
