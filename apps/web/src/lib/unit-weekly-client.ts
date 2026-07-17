/* Client API báo cáo tuần đơn vị (thu mua · tiêu thụ–tồn kho).
   - Đơn vị thành viên: `/api/member/weekly-report` (server ép company ∈ đơn vị được gán).
   - Chuyên viên có quyền `unit_weekly`: `/api/unit-weekly` (xem/sửa mọi đơn vị + chỉ tiêu kế hoạch). */

import { apiFetch } from "./http";
import type { Kind, Values } from "./unit-weekly-fields";

export type WeeklyEntry = { fields: Values; updated_at: string; updated_by: string | null };
export type WeekData = {
  week_key: string;
  today_week: string;
  edit_window_days: number;
  units: string[];
  plans: Record<string, number>;            // chỉ tiêu kế hoạch thu mua năm (đơn vị: tấn)
  entries: Record<string, WeeklyEntry | null>;
};
export type TimelineRow = { week_key: string; company: string; fields: Values; updated_at: string; updated_by: string | null };
export type Timeline = {
  today_week: string; edit_window_days: number; units: string[];
  plans: Record<string, number>; entries: TimelineRow[];
};
export type PlanData = { year: number; units: string[]; plans: Record<string, number> };

const J = { "Content-Type": "application/json" };

// ── Đơn vị thành viên (chỉ đơn vị được gán) ──
export const fetchMyWeek = (kind: Kind, weekKey: string) =>
  apiFetch<WeekData>(`/api/member/weekly-report?kind=${kind}&week_key=${weekKey}`);

export const fetchMyWeeklyTimeline = (kind: Kind, weeks = 16) =>
  apiFetch<Timeline>(`/api/member/weekly-report/timeline?kind=${kind}&weeks=${weeks}`);

export const saveMyWeekly = (kind: Kind, company: string, weekKey: string, fields: Values, createOnly = false) =>
  apiFetch<{ ok: boolean }>(`/api/member/weekly-report`, {
    method: "PUT", headers: J,
    body: JSON.stringify({ kind, company, week_key: weekKey, fields, create_only: createOnly }),
  });

// ── Chuyên viên có quyền (mọi đơn vị) ──
export const fetchWeek = (kind: Kind, weekKey: string) =>
  apiFetch<WeekData>(`/api/unit-weekly/week?kind=${kind}&week_key=${weekKey}`);

export const fetchWeeklyTimeline = (kind: Kind, weeks = 16) =>
  apiFetch<Timeline>(`/api/unit-weekly/timeline?kind=${kind}&weeks=${weeks}`);

export const saveWeekly = (kind: Kind, company: string, weekKey: string, fields: Values, createOnly = false) =>
  apiFetch<{ ok: boolean }>(`/api/unit-weekly/report`, {
    method: "PUT", headers: J,
    body: JSON.stringify({ kind, company, week_key: weekKey, fields, create_only: createOnly }),
  });

export const fetchPlan = (year: number) => apiFetch<PlanData>(`/api/unit-weekly/plan?year=${year}`);

export const savePlan = (year: number, company: string, planTonnes: number | null) =>
  apiFetch<{ ok: boolean }>(`/api/unit-weekly/plan`, {
    method: "PUT", headers: J,
    body: JSON.stringify({ year, company, plan_tonnes: planTonnes }),
  });
