/* Dữ liệu + lưu của màn Kế hoạch năm: nạp · sửa nháp · lưu khi rời ô (chỉ các ô đổi) · khoá theo chốt
   số liệu và gửi «Đề nghị sửa» cho đơn vị đã chốt (03/10/2026). Màn gọi PHẢI render `modal`. */

import { message } from "antd";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { type Role, type YearPlanRow, fetchYearPlan, saveYearPlan } from "../../../lib/unit-daily-client";
import { type EditRequestDraft, useEditRequest } from "../../../lib/use-edit-request";
import { EMPTY_PLAN as EMPTY, changedPlanValues } from "./year-plan-fields";
import { syncRevenueTotal } from "./year-plan-sections";

export function useYearPlan(role: Role, year: number, canEditField: (k: keyof YearPlanRow) => boolean) {
  const [units, setUnits] = useState<string[]>([]);
  const [plans, setPlans] = useState<Record<string, YearPlanRow>>({});
  const [saved, setSaved] = useState<Record<string, YearPlanRow>>({});   // số đang lưu (để biết ô nào đổi)
  const [locked, setLocked] = useState<Record<string, boolean>>({});
  const [lockedUntil, setLockedUntil] = useState<Record<string, string | null>>({});
  const [requesting, setRequesting] = useState<string | null>(null);     // đơn vị đang soạn đề nghị sửa
  const [loading, setLoading] = useState(false);
  const [savingUnit, setSavingUnit] = useState<string | null>(null);
  const { saveOrRequest, request, modal } = useEditRequest();
  // Lượt nạp: tăng mỗi lần `load` (đổi năm / nạp lại). Lần lưu hay lần nạp xong muộn mà lượt đã đổi thì
  // bỏ kết quả — không thì số của năm cũ đè lên bảng năm mới.
  const genRef = useRef(0);

  const load = useCallback(() => {
    const gen = ++genRef.current;
    setLoading(true);
    fetchYearPlan(role, year)
      .then((d) => {
        if (gen !== genRef.current) return;
        // Đủ khoá cho mọi đơn vị (server cũ / bản ghi thiếu ô mới → null), để so "đã đổi" cho đúng.
        const full = Object.fromEntries(Object.entries(d.plans ?? {}).map(([u, r]) => [u, { ...EMPTY, ...r }]));
        setUnits(d.units); setPlans(full); setSaved(full);
        setLocked(d.locked ?? {}); setLockedUntil(d.locked_until ?? {}); setRequesting(null);
      })
      .catch((e) => { if (gen === genRef.current) message.error(e.message); })
      .finally(() => { if (gen === genRef.current) setLoading(false); });
  }, [role, year]);
  useEffect(() => { load(); }, [load]);

  const rowOf = (u: string): YearPlanRow => plans[u] ?? EMPTY;

  /** Sửa 1 ô trong nháp (chưa gọi API) — lưu khi rời ô. Tham chiếu cố định để ô nhập `memo` không vẽ lại. */
  const setCell = useCallback((u: string, key: keyof YearPlanRow, v: number | null) =>
    setPlans((p) => ({ ...p, [u]: { ...(p[u] ?? EMPTY), [key]: v } })), []);

  const rowLocked = (u: string) => role === "member" && !!locked[u];
  const cellEditable = (u: string, key: keyof YearPlanRow) =>
    canEditField(key) && (!rowLocked(u) || requesting === u);

  /** Nội dung đề nghị sửa = các ô ĐÃ ĐỔI so với số đang lưu (null = xoá ô). */
  const draftOf = (u: string): EditRequestDraft => ({
    op: "year_plan", title: `Kế hoạch năm ${year} — ${u}`, company: u, dates: [`${year}-01-01`],
    payload: { year, company: u, ...changedPlanValues(rowOf(u), saved[u] ?? EMPTY, canEditField) },
  });

  /** Lưu khi rời ô: CHỈ gửi các ô khác số đang lưu (null = xoá); không đổi gì thì không gọi API.
      Gửi cả hàng sẽ ghi đè `plan_revenue_ty` của đơn vị cũ chỉ có tổng (luật doanh thu ở server). */
  const save = async (u: string) => {
    if (rowLocked(u)) return;   // cột đã chốt: chỉ gửi qua «Gửi đề nghị», không tự lưu khi rời ô
    const changed = changedPlanValues(rowOf(u), saved[u] ?? EMPTY, canEditField);
    if (Object.keys(changed).length === 0) return;
    const gen = genRef.current;
    setSavingUnit(u);
    try {
      // Vừa bị chốt sau lúc mở trang → server chặn → mở thẳng popup đề nghị sửa với đúng số vừa gõ.
      const r = await saveOrRequest(() => saveYearPlan(role, year, u, changed), () => draftOf(u));
      if (gen !== genRef.current) return;   // đã đổi năm / nạp lại trong lúc lưu: số đã ghi, bảng đang là lượt khác
      if (r === "saved") {
        message.success(`Đã lưu kế hoạch ${year} — ${u}`);
        // Số đã lưu = số cũ + đúng các ô vừa gửi (ô gõ thêm trong lúc chờ vẫn là "đã đổi", lưu ở lần rời ô sau).
        setSaved((p) => ({ ...p, [u]: syncRevenueTotal({ ...(p[u] ?? EMPTY), ...changed }, changed) }));
        setPlans((p) => ({ ...p, [u]: syncRevenueTotal(p[u] ?? EMPTY, changed) }));
      } else load();
    } catch (e) {
      message.error((e as Error).message);
      if (gen === genRef.current) load(); // hỏng thì nạp lại số thật (lượt khác thì `load` này là của năm cũ)
    } finally {
      setSavingUnit(null);
    }
  };

  const sendRequest = async (u: string) => {
    const d = draftOf(u);
    if (Object.keys(d.payload).length <= 2) { message.info("Chưa đổi ô nào — sửa số trước khi gửi đề nghị."); return; }
    setSavingUnit(u);
    try {
      if (await request(d) === "requested") load();
    } finally {
      setSavingUnit(null);
    }
  };

  const cancelRequest = (u: string) => {
    setRequesting(null);
    setPlans((p) => ({ ...p, [u]: saved[u] ?? EMPTY }));
  };
  const anyLocked = role === "member" && units.some((u) => locked[u]);

  // «Rời ô → lưu» với tham chiếu CỐ ĐỊNH (ô nhập là `memo`), gọi bản `save` mới nhất qua ref.
  const saveRef = useRef(save);
  useLayoutEffect(() => { saveRef.current = save; });
  const saveOnLeave = useCallback((u: string) => { void saveRef.current(u); }, []);

  return {
    units, locked, lockedUntil, requesting, setRequesting, loading, savingUnit, load, rowOf, setCell,
    cellEditable, rowLocked, saveOnLeave, sendRequest, cancelRequest, anyLocked, modal,
  };
}
