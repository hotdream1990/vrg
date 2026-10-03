/* Trạng thái màn soạn bản nháp giá sàn (Nháp → Dự thảo → Tờ trình → Áp dụng): nạp · sửa (đánh dấu chưa
   lưu) · lưu · chuyển bước · xoá · xem trước. Mỗi bước chỉ gửi phần sửa được của bước đó (server chặn
   phần khác). Giữ hàng đợi áp phương án (useProposalApply) ở đây để Lưu/Xem trước CHỜ các lần sửa ô
   đang gửi xong. `rev` đếm số lần sửa: có sửa trong lúc đang lưu thì lưu xong chỉ cập nhật mốc
   `updated_at`, không đè form và giữ cờ chưa lưu. */

import { useCallback, useEffect, useRef, useState } from "react";

import { type Memo, type Sheet, type Stage, moveStage } from "../../../lib/floor-draft-flow-client";
import {
  type Draft, type DraftUpdate, type Proposal, deleteDraft, fetchDraftHtml, getDraft, previewProposalHtml,
  updateDraft,
} from "../../../lib/floor-proposal-client";
import { useProposalApply } from "./components/useProposalApply";

export type DraftForm = { title: string; note: string; proposal: Proposal; sheet: Sheet | null; memo: Memo | null };

const toForm = (d: Draft): DraftForm => ({
  title: d.title ?? "", note: d.note ?? "", proposal: d.proposal, sheet: d.sheet, memo: d.memo,
});

/** Bỏ đoạn trống (cả lead lẫn chữ) trước khi lưu — in lên tờ trình thành dòng thừa. */
const cleanMemo = (m: Memo): Memo => {
  const keep = (ps: Memo["futures"]) => ps.filter((p) => p.lead.trim() || p.text.trim());
  return { ...m, futures: keep(m.futures), physical: keep(m.physical), outlook: keep(m.outlook) };
};

export function useFloorDraft(id: number) {
  const [draft, setDraftState] = useState<Draft | null>(null);
  const [form, setForm] = useState<DraftForm | null>(null);
  const [dirty, setDirtyState] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  // Ref luôn giữ bản MỚI NHẤT (cập nhật đồng bộ) — lưu/xem trước đọc ở đây, không đọc closure cũ.
  const formRef = useRef<DraftForm | null>(null);
  const draftRef = useRef<Draft | null>(null);
  const dirtyRef = useRef(false);
  const rev = useRef(0);

  const setDraft = useCallback((d: Draft) => { draftRef.current = d; setDraftState(d); }, []);
  const setDirty = useCallback((v: boolean) => { dirtyRef.current = v; setDirtyState(v); }, []);

  const reset = useCallback((d: Draft) => {
    const f = toForm(d);
    formRef.current = f;
    setDraft(d); setForm(f); setDirty(false);
  }, [setDraft, setDirty]);

  const reload = useCallback(async () => reset(await getDraft(id)), [id, reset]);

  useEffect(() => {
    if (!Number.isFinite(id) || id <= 0) { setErr("Mã bản nháp không hợp lệ."); setLoading(false); return; }
    let cancelled = false;
    setLoading(true); setErr("");
    getDraft(id)
      .then((d) => { if (!cancelled) reset(d); })
      .catch((e) => { if (!cancelled) setErr(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id, reset]);

  const patch = useCallback((p: Partial<DraftForm>) => {
    if (!formRef.current) return;
    const next = { ...formRef.current, ...p };
    formRef.current = next;
    rev.current += 1;
    setForm(next);
    setDirty(true);
  }, [setDirty]);
  const setProposal = useCallback((proposal: Proposal) => patch({ proposal }), [patch]);
  const applier = useProposalApply(form?.proposal ?? null, setProposal);
  const { whenIdle } = applier;

  /** Ném lỗi để nơi gọi báo (409 = người khác đã lưu sau mốc mình mở; 400 = sửa sai bước). */
  const save = useCallback(async () => {
    setSaving(true);
    try {
      await whenIdle();                       // ô vừa sửa (blur khi bấm Lưu) phải vào bản lưu
      const f = formRef.current;
      const stage = draftRef.current?.stage;
      if (!f || !stage) return;
      const revAtSend = rev.current;
      const body: DraftUpdate = {
        title: f.title.trim(), note: f.note.trim() || null, proposal: f.proposal,
        base_updated_at: draftRef.current?.updated_at,
      };
      if (stage === "du_thao" && f.sheet) body.sheet = f.sheet;
      if (stage === "to_trinh" && f.memo) body.memo = cleanMemo(f.memo);
      const d = await updateDraft(id, body);
      if (rev.current === revAtSend) reset(d);
      else setDraft(d);                        // có sửa trong lúc lưu → giữ form + cờ chưa lưu
    } finally {
      setSaving(false);
    }
  }, [id, reset, setDraft, whenIdle]);

  /** Lưu nếu còn thay đổi — trước khi chuyển bước / tải tệp (tệp dựng từ bản đã lưu). */
  const ensureSaved = useCallback(async () => {
    await whenIdle();
    if (dirtyRef.current) await save();
  }, [save, whenIdle]);

  const move = useCallback(async (to: Stage, note?: string) => {
    await ensureSaved();
    reset(await moveStage(id, to, draftRef.current?.updated_at, note));
  }, [ensureSaved, id, reset]);

  const remove = useCallback(async () => {
    await deleteDraft(id);
    setDirty(false);
  }, [id, setDirty]);

  /** Tờ trình để xem trước/in: có thay đổi chưa lưu → dựng từ nội dung đang sửa (kèm ảnh chụp số
   *  thị trường của bản nháp); không → bản đã lưu. */
  const previewHtml = useCallback(async () => {
    await whenIdle();
    const f = formRef.current;
    if (!f || !dirtyRef.current) return fetchDraftHtml(id);
    return previewProposalHtml({ draft_id: id, proposal: f.proposal, memo: f.memo ? cleanMemo(f.memo) : undefined });
  }, [id, whenIdle]);

  return {
    draft, form, dirty, loading, saving, err, applier, patch, save, ensureSaved, move, remove, reload, previewHtml,
  };
}
