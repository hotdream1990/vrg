/* Trạng thái bản nháp Báo cáo tuần: mở tuần, sửa narrative, TỰ LƯU (debounce) và nhận lại bảng số
   máy chủ dựng theo narrative mới (đổi số tuần gộp → bảng/nhãn đổi theo).

   Bảo toàn chữ đang gõ: phần chờ lưu nằm ở pendingRef — đổi tuần thì lưu ngay trước khi mở tuần
   khác, rời trang thì gửi lưu không chờ, đóng tab thì trình duyệt hỏi lại. Các lượt PUT xếp hàng
   (lượt sau chạy sau khi lượt trước xong) để bản cũ không bao giờ ghi đè bản mới. */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  type MacroSection,
  type WeeklyNarrative,
  type WeeklyReport,
  getWeeklyReport,
  saveWeeklyReport,
} from "../../../../lib/weekly-report-client";

export type SaveState = "idle" | "saving" | "saved" | "error";
type Pending = { week_key: string; narrative: WeeklyNarrative };
const DEBOUNCE_MS = 900;

/** Mọi phần TỰ TÍNH của report (bảng, nhãn, gaps, cao/thấp, tỷ giá, mủ nước…) — giữ narrative đang gõ. */
function pickTables(r: WeeklyReport): Omit<WeeklyReport, "narrative"> {
  const { narrative: _ignored, ...auto } = r;
  return auto;
}

/** `onSaved(r)`: gọi sau mỗi lượt lưu thành công của tuần đang mở (trang tự quyết có nạp lại danh sách không). */
export function useWeeklyDraft(canEdit: boolean, onSaved: (r: WeeklyReport) => void) {
  const [draft, setDraft] = useState<WeeklyReport | null>(null);
  const [save, setSave] = useState<SaveState>("idle");
  const [savedAt, setSavedAt] = useState("");
  const [saveError, setSaveError] = useState("");
  // So với narrative ĐÃ GỬI (không phải bản máy chủ trả về — máy chủ bổ sung field mặc định).
  const lastSaved = useRef("");
  const weekRef = useRef<string | null>(null);        // tuần đang mở
  const lastReport = useRef<WeeklyReport | null>(null);
  const pendingRef = useRef<Pending | null>(null);    // thay đổi chưa gửi
  const inflight = useRef<Promise<unknown>>(Promise.resolve());
  const inflightCount = useRef(0);
  const seqRef = useRef(0);                            // lượt open() mới nhất
  const blocked = useRef(false);                       // đang xoá báo cáo → không tự lưu
  const timer = useRef<number | null>(null);
  const onSavedRef = useRef(onSaved);
  onSavedRef.current = onSaved;

  const clearTimer = () => { if (timer.current) { clearTimeout(timer.current); timer.current = null; } };

  /** Lưu 1 lượt — nối SAU lượt đang chạy. */
  const persist = useCallback((weekKey: string, narrative: WeeklyNarrative): Promise<WeeklyReport> => {
    const json = JSON.stringify(narrative);
    const run = async () => {
      inflightCount.current += 1;
      if (weekRef.current === weekKey) setSave("saving");
      try {
        const r = await saveWeeklyReport(weekKey, narrative);
        if (weekRef.current === weekKey) {
          lastSaved.current = json;
          lastReport.current = r;
          setDraft((d) => (d && d.week_key === r.week_key ? { ...d, ...pickTables(r) } : d));
          setSave("saved"); setSavedAt(new Date().toLocaleTimeString("vi-VN")); setSaveError("");
          onSavedRef.current(r);
        }
        return r;
      } catch (e) {
        if (weekRef.current === weekKey) { setSave("error"); setSaveError(e instanceof Error ? e.message : "Lỗi lưu"); }
        throw e;
      } finally {
        inflightCount.current -= 1;
      }
    };
    const p = inflight.current.then(run, run);
    inflight.current = p.catch(() => undefined);
    return p;
  }, []);

  /** Gửi ngay phần đang chờ (nếu có). */
  const sendPending = useCallback(() => {
    const p = pendingRef.current;
    clearTimer(); pendingRef.current = null;
    return p ? persist(p.week_key, p.narrative) : null;
  }, [persist]);

  useEffect(() => {
    if (!draft || !canEdit || blocked.current) return;
    if (JSON.stringify(draft.narrative) === lastSaved.current) { pendingRef.current = null; return; }
    pendingRef.current = { week_key: draft.week_key, narrative: draft.narrative };
    clearTimer();
    timer.current = window.setTimeout(() => { sendPending()?.catch(() => undefined); }, DEBOUNCE_MS);
    return clearTimer;
  }, [draft, canEdit, sendPending]);

  // Rời trang: gửi lưu không chờ · đóng tab/tải lại khi còn thay đổi chưa lưu: trình duyệt hỏi lại.
  useEffect(() => {
    const onUnload = (e: BeforeUnloadEvent) => {
      if (!pendingRef.current && inflightCount.current === 0) return;
      e.preventDefault(); e.returnValue = "";
    };
    window.addEventListener("beforeunload", onUnload);
    return () => {
      window.removeEventListener("beforeunload", onUnload);
      sendPending()?.catch(() => undefined);
    };
  }, [sendPending]);

  /** Lưu NGAY phần còn chờ + chờ lượt đang chạy (trước AI / xuất PDF) → report mới nhất đã lưu. */
  const flush = useCallback(async (): Promise<WeeklyReport | null> => {
    if (!canEdit) return lastReport.current;
    await (sendPending() ?? inflight.current);
    await inflight.current;
    return lastReport.current;
  }, [canEdit, sendPending]);

  const open = useCallback(async (weekKey: string): Promise<WeeklyReport | null> => {
    const seq = ++seqRef.current;
    await sendPending();            // lưu lỗi → ném lỗi, ở lại tuần cũ để không mất chữ
    const r = await getWeeklyReport(weekKey);
    if (seq !== seqRef.current) return null;   // đã bấm mở tuần khác sau lượt này
    weekRef.current = r.week_key; lastReport.current = r; blocked.current = false;
    lastSaved.current = JSON.stringify(r.narrative);
    setSave("idle"); setSavedAt(""); setSaveError(""); setDraft(r);
    return r;
  }, [sendPending]);

  /** Trước khi XOÁ báo cáo: bỏ lượt hẹn giờ + phần chờ, chờ PUT đang chạy xong (tránh tạo lại báo cáo). */
  const cancel = useCallback(async () => {
    blocked.current = true; clearTimer(); pendingRef.current = null;
    await inflight.current;
  }, []);
  /** Xoá thất bại → bật lại tự lưu. */
  const resume = useCallback(() => { blocked.current = false; setDraft((d) => d && { ...d }); }, []);

  const close = useCallback(() => {
    seqRef.current += 1; weekRef.current = null; lastReport.current = null;
    lastSaved.current = ""; pendingRef.current = null; blocked.current = false; setDraft(null);
  }, []);

  /** `wk`: chỉ áp nếu tuần đang mở đúng là tuần này (kết quả AI về muộn sau khi đổi tuần). */
  const setNar = useCallback((patch: Partial<WeeklyNarrative>, wk?: string) =>
    setDraft((d) => (d && (!wk || d.week_key === wk) ? { ...d, narrative: { ...d.narrative, ...patch } } : d)), []);

  const setMacro = useCallback((i: number, patch: Partial<MacroSection>, wk?: string) =>
    setDraft((d) => {
      if (!d || (wk && d.week_key !== wk)) return d;
      const macro = d.narrative.macro.map((m, idx) => (idx === i ? { ...m, ...patch } : m));
      return { ...d, narrative: { ...d.narrative, macro } };
    }), []);

  /** Đổi số tuần gộp: co/giãn list override mủ nước theo số cột mới; chưa có list thì để nguyên. */
  const setSpan = useCallback((span: number) =>
    setDraft((d) => {
      if (!d) return d;
      const n = d.narrative;
      const fit = (a: (string | null)[] | null | undefined, len: number) =>
        (Array.isArray(a) ? Array.from({ length: len }, (_, i) => a[i] ?? null) : a);
      return {
        ...d,
        narrative: {
          ...n, span_weeks: span,
          latex_override: fit(n.latex_override, span + 1),
          latex_change_override: fit(n.latex_change_override, span),
        },
      };
    }), []);

  const currentWeek = useCallback(() => weekRef.current, []);

  return {
    draft, save, savedAt, saveError, open, close, cancel, resume, flush, currentWeek, setNar, setMacro, setSpan,
  };
}
