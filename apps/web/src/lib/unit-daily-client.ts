/* Client API báo cáo tiêu thụ–tồn kho theo ngày (thu mua · tiêu thụ–tồn kho).
   - Đơn vị thành viên: `/api/member/daily-report` (server ép company ∈ đơn vị được gán).
   - Chuyên viên có quyền `unit_daily`: `/api/unit-daily` (xem/sửa mọi đơn vị + chỉ tiêu kế hoạch). */

import { authHeaders } from "./auth-token";
import { API, apiFetch } from "./http";
import type { Kind, Values } from "./unit-daily-fields";

type Role = "member" | "hq";
const contractBase = (role: Role) =>
  role === "member" ? "/api/member/daily-report/contract-file" : "/api/unit-daily/contract-file";

/** Upload file Hợp đồng (PDF/ảnh) — trả tên file lưu (uuid) + tên gốc để gắn vào dòng tồn kho. */
export const uploadContractFile = (role: Role, file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return apiFetch<{ file: string; filename: string; size: number }>(contractBase(role), { method: "POST", body: fd });
};

/** Mở file Hợp đồng đã upload trong tab mới (fetch kèm token → blob). */
export async function openContractFile(role: Role, name: string): Promise<void> {
  const res = await fetch(`${API}${contractBase(role)}/${encodeURIComponent(name)}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Không tải được file hợp đồng.");
  const url = URL.createObjectURL(await res.blob());
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export type DailyEntry = { fields: Values; updated_at: string; updated_by: string | null };
/** Đơn giá thu mua ĐÚNG NGÀY (đồng/độ TSC), link từ "Giá mủ nguyên liệu". */
export type UnitPurchasePrice = { latex: number | null; cup: number | null };
/** Đơn giá VND (mủ nước/mủ chén) do form Thu mua ghi về kho "Giá mủ nguyên liệu". */
export type PriceDraft = UnitPurchasePrice;
export type DayData = {
  as_of: string;
  today: string;
  edit_window_days: number;
  units: string[];
  plans: Record<string, number>;            // chỉ tiêu kế hoạch thu mua năm (đơn vị: tấn)
  entries: Record<string, DailyEntry | null>;
  currencies?: Record<string, string>;      // {đơn vị: VND/LAK/KHR} — ≠VND ⇒ hiện ô tỷ giá
  factories?: Record<string, boolean>;      // {đơn vị: có nhà máy?} — false ⇒ hiện tồn kho nguyên liệu
  prices?: Record<string, UnitPurchasePrice>; // {đơn vị: đơn giá mủ nước/mủ chén} (chỉ kind=purchase)
};
export type TimelineRow = {
  as_of: string; company: string; fields: Values; updated_at: string; updated_by: string | null;
  prices?: UnitPurchasePrice;   // đơn giá mủ nước/mủ chén đúng ngày (link, chỉ đọc — chỉ kind=purchase)
};
export type Timeline = {
  today: string; edit_window_days: number; units: string[];
  plans: Record<string, number>; entries: TimelineRow[];
};
export type PlanData = { year: number; units: string[]; plans: Record<string, number> };

const J = { "Content-Type": "application/json" };

// ── Đơn vị thành viên (chỉ đơn vị được gán) ──
export const fetchMyDay = (kind: Kind, asOf: string) =>
  apiFetch<DayData>(`/api/member/daily-report?kind=${kind}&as_of=${asOf}`);

export const fetchMyDailyTimeline = (kind: Kind, days = 90) =>
  apiFetch<Timeline>(`/api/member/daily-report/timeline?kind=${kind}&days=${days}`);

export const saveMyDaily = (kind: Kind, company: string, asOf: string, fields: Values, createOnly = false) =>
  apiFetch<{ ok: boolean }>(`/api/member/daily-report`, {
    method: "PUT", headers: J,
    body: JSON.stringify({ kind, company, as_of: asOf, fields, create_only: createOnly }),
  });

// ── Chuyên viên có quyền (mọi đơn vị) ──
export const fetchDay = (kind: Kind, asOf: string) =>
  apiFetch<DayData>(`/api/unit-daily/day?kind=${kind}&as_of=${asOf}`);

export const fetchDailyTimeline = (kind: Kind, days = 90) =>
  apiFetch<Timeline>(`/api/unit-daily/timeline?kind=${kind}&days=${days}`);

export const saveDaily = (kind: Kind, company: string, asOf: string, fields: Values, createOnly = false) =>
  apiFetch<{ ok: boolean }>(`/api/unit-daily/report`, {
    method: "PUT", headers: J,
    body: JSON.stringify({ kind, company, as_of: asOf, fields, create_only: createOnly }),
  });

export const fetchPlan = (year: number) => apiFetch<PlanData>(`/api/unit-daily/plan?year=${year}`);

export const savePlan = (year: number, company: string, planTonnes: number | null) =>
  apiFetch<{ ok: boolean }>(`/api/unit-daily/plan`, {
    method: "PUT", headers: J,
    body: JSON.stringify({ year, company, plan_tonnes: planTonnes }),
  });
