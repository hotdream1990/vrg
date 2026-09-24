/* Trạng thái màn soạn Bản nháp tờ trình: nạp · sửa (đánh dấu chưa lưu) · lưu · xoá · xem trước.
   Giữ hàng đợi áp phương án (useProposalApply) ở đây để Lưu/Xem trước CHỜ các lần sửa ô đang gửi
   xong rồi mới đọc phương án mới nhất. `rev` đếm số lần sửa: có sửa trong lúc đang lưu thì lưu
   xong chỉ cập nhật mốc `updated_at`, không đè form và giữ cờ chưa lưu. */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  type Draft, type Proposal, deleteDraft, fetchDraftHtml, getDraft, previewProposalHtml, updateDraft,
} from "../../../lib/floor-proposal-client";
import { useProposalApply } from "./components/useProposalApply";

export type DraftForm = { title: string; note: string; proposal: Proposal; n1: string[]; n2: string[] };

const toForm = (d: Draft): DraftForm => ({
  title: d.title ?? "", note: d.note ?? "", proposal: d.proposal,
  n1: d.doc?.n1 ?? [], n2: d.doc?.n2 ?? [],
});

/** Bỏ đoạn trống (kể cả đoạn chỉ có gạch đầu dòng) trước khi lưu — in lên tờ trình thành dòng thừa. */
const cleanParas = (ps: string[]) => ps.map((p) => p.trim()).filter((p) => p && !/^[-–•\s]+$/.test(p));

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

  /** Ném lỗi để nơi gọi báo (409 = người khác đã lưu sau mốc mình mở). */
  const save = useCallback(async () => {
    setSaving(true);
    try {
      await whenIdle();                       // ô vừa sửa (blur khi bấm Lưu) phải vào bản lưu
      const f = formRef.current;
      if (!f) return;
      const revAtSend = rev.current;
      const d = await updateDraft(id, {
        title: f.title.trim(), note: f.note.trim() || null, proposal: f.proposal,
        n1: cleanParas(f.n1), n2: cleanParas(f.n2), base_updated_at: draftRef.current?.updated_at,
      });
      if (rev.current === revAtSend) reset(d);
      else setDraft(d);                        // có sửa trong lúc lưu → giữ form + cờ chưa lưu
    } finally {
      setSaving(false);
    }
  }, [id, reset, setDraft, whenIdle]);

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
    return previewProposalHtml({ draft_id: id, proposal: f.proposal, n1: cleanParas(f.n1), n2: cleanParas(f.n2) });
  }, [id, whenIdle]);

  return { draft, form, dirty, loading, saving, err, applier, patch, save, remove, reload, previewHtml };
}
