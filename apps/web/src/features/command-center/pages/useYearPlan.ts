/* Dữ liệu + lưu của màn Kế hoạch năm: nạp · sửa nháp · lưu khi rời ô · khoá theo chốt số liệu và gửi
   «Đề nghị sửa» cho dòng đã chốt (03/10/2026). Màn gọi PHẢI render `modal` (popup gửi đề nghị). */

import { message } from "antd";
import { useCallback, useEffect, useState } from "react";

import { type Role, type YearPlanRow, fetchYearPlan, saveYearPlan } from "../../../lib/unit-daily-client";
import { type EditRequestDraft, useEditRequest } from "../../../lib/use-edit-request";
import { EMPTY_PLAN as EMPTY, changedPlanValues } from "./year-plan-fields";

export function useYearPlan(role: Role, year: number, canEditField: (k: keyof YearPlanRow) => boolean) {
  const [units, setUnits] = useState<string[]>([]);
  const [plans, setPlans] = useState<Record<string, YearPlanRow>>({});
  const [saved, setSaved] = useState<Record<string, YearPlanRow>>({});   // số đang lưu (để biết ô nào đổi)
  const [locked, setLocked] = useState<Record<string, boolean>>({});
  const [lockedUntil, setLockedUntil] = useState<Record<string, string | null>>({});
  const [requesting, setRequesting] = useState<string | null>(null);     // dòng đang soạn đề nghị sửa
  const [loading, setLoading] = useState(false);
  const [savingUnit, setSavingUnit] = useState<string | null>(null);
  const { saveOrRequest, request, modal } = useEditRequest();

  const load = useCallback(() => {
    setLoading(true);
    fetchYearPlan(role, year)
      .then((d) => {
        setUnits(d.units); setPlans(d.plans ?? {}); setSaved(d.plans ?? {});
        setLocked(d.locked ?? {}); setLockedUntil(d.locked_until ?? {}); setRequesting(null);
      })
      .catch((e) => message.error(e.message))
      .finally(() => setLoading(false));
  }, [role, year]);
  useEffect(() => { load(); }, [load]);

  const rowOf = (u: string): YearPlanRow => plans[u] ?? EMPTY;

  /** Sửa 1 ô trong nháp (chưa gọi API) — lưu khi rời ô. */
  const setCell = (u: string, key: keyof YearPlanRow, v: number | null) =>
    setPlans((p) => ({ ...p, [u]: { ...rowOf(u), [key]: v } }));

  const rowLocked = (u: string) => role === "member" && !!locked[u];
  const cellEditable = (u: string, key: keyof YearPlanRow) =>
    canEditField(key) && (!rowLocked(u) || requesting === u);

  /** Nội dung đề nghị sửa = các ô ĐÃ ĐỔI so với số đang lưu (null = xoá ô). */
  const draftOf = (u: string): EditRequestDraft => ({
    op: "year_plan", title: `Kế hoạch năm ${year} — ${u}`, company: u, dates: [`${year}-01-01`],
    payload: { year, company: u, ...changedPlanValues(rowOf(u), saved[u] ?? EMPTY, canEditField) },
  });

  const save = async (u: string) => {
    if (rowLocked(u)) return;   // dòng đã chốt: chỉ gửi qua «Gửi đề nghị», không tự lưu khi rời ô
    setSavingUnit(u);
    try {
      // Vừa bị chốt sau lúc mở trang → server chặn → mở thẳng popup đề nghị sửa với đúng số vừa gõ.
      const r = await saveOrRequest(() => saveYearPlan(role, year, u, rowOf(u)), () => draftOf(u));
      if (r === "saved") {
        message.success(`Đã lưu kế hoạch ${year} — ${u}`);
        setSaved((p) => ({ ...p, [u]: rowOf(u) }));
      } else load();
    } catch (e) {
      message.error((e as Error).message);
      load(); // hỏng thì nạp lại số thật
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

  return {
    units, locked, lockedUntil, requesting, setRequesting, loading, savingUnit, load, rowOf, setCell,
    cellEditable, rowLocked, save, sendRequest, cancelRequest, anyLocked, modal,
  };
}
