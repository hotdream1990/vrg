/* Client API báo cáo tiêu thụ–tồn kho theo ngày (thu mua · tiêu thụ–tồn kho).
   - Đơn vị thành viên: `/api/member/daily-report` (server ép company ∈ đơn vị được gán).
   - Chuyên viên có quyền `unit_daily`: `/api/unit-daily` (xem/sửa mọi đơn vị + chỉ tiêu kế hoạch). */

import { authHeaders } from "./auth-token";
import { API, apiFetch } from "./http";
import type { Kind, Values } from "./unit-daily-fields";

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

/** Vai trò gọi API: đơn vị thành viên (chỉ đơn vị mình) hay chuyên viên/HQ (mọi đơn vị). */
export type Role = "member" | "hq";

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
/** Số liệu NĂM của 1 đơn vị (nhập 1 lần, cập nhật khi có thay đổi). */
export type YearPlanRow = {
  plan_tonnes: number | null;        // kế hoạch thu mua năm (tấn)
  signed_lt_tonnes: number | null;   // tổng SL đã ký HĐ dài hạn (tấn)
  carry_lt_tonnes: number | null;    // HĐ dài hạn năm trước chuyển sang (tấn)
  carry_spot_tonnes: number | null;  // HĐ chuyến năm trước chuyển sang (tấn)
};
export type YearPlanData = { year: number; units: string[]; plans: Record<string, YearPlanRow> };

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

// ── Số liệu NĂM (kế hoạch thu mua + HĐ dài hạn đã ký) — đơn vị tự cập nhật, chuyên viên xem/sửa mọi đơn vị ──
const planBase = (role: Role) => (role === "member" ? "/api/member/plan" : "/api/unit-daily/plan");

export const fetchYearPlan = (role: Role, year: number) =>
  apiFetch<YearPlanData>(`${planBase(role)}?year=${year}`);

export const saveYearPlan = (role: Role, year: number, company: string, row: YearPlanRow) =>
  apiFetch<{ ok: boolean }>(planBase(role), {
    method: "PUT", headers: J,
    body: JSON.stringify({ year, company, ...row }),
  });

// ── Báo cáo tổng hợp theo KỲ (tuần/tháng/năm/khoảng tự chọn) — trích xuất từ số liệu ngày ──
export type PeriodRow = {
  company: string; region: string | null; days: number; last_day: string | null;
  stock_by_grade?: Record<string, number | null>;
  [key: string]: unknown;
};
export type PeriodReport = {
  kind: Kind; date_from: string; date_to: string; grades: string[]; rows: PeriodRow[];
};

// CHỈ chuyên viên/admin có quyền `unit_daily` — đơn vị thành viên không có màn này.
const PERIOD_BASE = "/api/unit-daily/period-report";

export const fetchPeriodReport = (kind: Kind, dateFrom: string, dateTo: string) =>
  apiFetch<PeriodReport>(`${PERIOD_BASE}?kind=${kind}&date_from=${dateFrom}&date_to=${dateTo}`);

/** Tải Excel báo cáo kỳ (bám mẫu Biểu (1)/(2)) — fetch kèm token rồi lưu file. */
export async function downloadPeriodXlsx(
  kind: Kind, dateFrom: string, dateTo: string,
): Promise<void> {
  const url = `${API}${PERIOD_BASE}.xlsx?kind=${kind}&date_from=${dateFrom}&date_to=${dateTo}`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error("Không tải được file Excel.");
  const blob = await res.blob();
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = `bao-cao-${kind === "purchase" ? "thu-mua" : "tieu-thu-ton-kho"}-${dateFrom}-den-${dateTo}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 60_000);
}

// ── Nhập liệu bằng Excel (tải mẫu · xem trước · ghi) ──
export type ImportKind = "purchase" | "sales" | "stock" | "plan";
export type ImportRow = {
  _row: number; _errors: string[]; _action?: "create" | "update";
  [key: string]: unknown;
};
export type ImportColumn = { key: string; title: string; unit: string };
export type ImportPreview = {
  kind: ImportKind; rows: ImportRow[]; columns: ImportColumn[];
  summary: { total: number; ok: number; error: number };
};

const importBase = (role: Role) =>
  role === "member" ? "/api/member/import" : "/api/unit-daily/import";

/** Tải file Excel mẫu của 1 loại biểu. */
export async function downloadImportTemplate(role: Role, kind: ImportKind): Promise<void> {
  const res = await fetch(`${API}${importBase(role)}/template?kind=${kind}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Không tải được file mẫu.");
  const href = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = href;
  a.download = `mau-nhap-${kind}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 60_000);
}

/** Đọc file người dùng chọn → dữ liệu XEM TRƯỚC (chưa ghi gì vào hệ thống). */
export async function previewImport(role: Role, kind: ImportKind, file: File): Promise<ImportPreview> {
  const fd = new FormData();
  fd.append("file", file);
  return apiFetch<ImportPreview>(`${importBase(role)}/preview?kind=${kind}`, { method: "POST", body: fd });
}

/** Ghi các dòng đã xem trước (server bỏ qua dòng lỗi + kiểm lại quyền đơn vị). */
export const commitImport = (role: Role, kind: ImportKind, rows: ImportRow[]) =>
  apiFetch<{ saved: number; skipped: number; warnings?: string[] }>(
    `${importBase(role)}/commit`,
    { method: "POST", headers: J, body: JSON.stringify({ kind, rows }) });
