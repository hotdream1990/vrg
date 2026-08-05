/* Client API báo cáo tiêu thụ–tồn kho theo ngày (thu mua · tiêu thụ–tồn kho).
   - Đơn vị thành viên: `/api/member/daily-report` (server ép company ∈ đơn vị được gán).
   - Chuyên viên có quyền `unit_daily`: `/api/unit-daily` (xem/sửa mọi đơn vị + chỉ tiêu kế hoạch). */

import { authHeaders } from "./auth-token";
import { API, apiFetch } from "./http";
import type { Ccy, StockQtyLine, StockSignedLine } from "./unit-daily-consumption";
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
/** Đơn giá thu mua ĐÚNG NGÀY (đồng/độ), link từ "Giá mủ nguyên liệu". */
export type UnitPurchasePrice = { latex: number | null; cup: number | null };
/** Mủ chén tính theo độ TSC hay độ DRC (đổi nhãn đơn vị lưu kèm giá). */
export type CupBasis = "tsc" | "drc";
/** Đơn giá VND (mủ nước/mủ chén) do form Thu mua ghi về kho "Giá mủ nguyên liệu". */
export type PriceDraft = UnitPurchasePrice & { cupBasis?: CupBasis };
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
  /** Tổng số dòng khớp khoảng ngày (server cắt trang, `entries` chỉ là trang đang xem). */
  total: number;
  /** false = biểu Thu mua, server trả trọn khoảng để dòng "Lũy kế" đúng (dữ liệu nhẹ). */
  paged: boolean;
  page: number; page_size: number;
};
/** Số liệu NĂM của 1 đơn vị (nhập 1 lần, cập nhật khi có thay đổi). */
export type YearPlanRow = {
  plan_tonnes: number | null;        // kế hoạch thu mua năm (tấn) — >0 là CÔNG TẮC bật màn Thu mua
  plan_sales_spot_tonnes: number | null;  // kế hoạch TIÊU THỤ cho HĐ chuyến (tấn)
  signed_lt_tonnes: number | null;   // tổng SL đã ký HĐ dài hạn (tấn)
  carry_lt_tonnes: number | null;    // HĐ dài hạn năm trước chuyển sang (tấn)
  carry_spot_tonnes: number | null;  // HĐ chuyến năm trước chuyển sang (tấn)
};
export type YearPlanData = { year: number; units: string[]; plans: Record<string, YearPlanRow> };

const J = { "Content-Type": "application/json" };

/** Bộ lọc thời gian timeline: preset `days` (mặc định) hoặc khoảng TỰ CHỌN `{from, to}`. */
export type TimelineRange = { days: number } | { from: string; to: string };

const timelineQuery = (kind: Kind, r: TimelineRange, page = 1, pageSize = 50): string => {
  const p = new URLSearchParams({ kind });
  if ("days" in r) p.set("days", String(r.days));
  else { p.set("date_from", r.from); p.set("date_to", r.to); }
  p.set("page", String(page));
  p.set("page_size", String(pageSize));
  return p.toString();
};

// ── Đơn vị thành viên (chỉ đơn vị được gán) ──
export const fetchMyDay = (kind: Kind, asOf: string) =>
  apiFetch<DayData>(`/api/member/daily-report?kind=${kind}&as_of=${asOf}`);

export const fetchMyDailyTimeline = (kind: Kind, range: TimelineRange = { days: 90 }, page = 1) =>
  apiFetch<Timeline>(`/api/member/daily-report/timeline?${timelineQuery(kind, range, page)}`);

export const saveMyDaily = (kind: Kind, company: string, asOf: string, fields: Values, createOnly = false) =>
  apiFetch<{ ok: boolean }>(`/api/member/daily-report`, {
    method: "PUT", headers: J,
    body: JSON.stringify({ kind, company, as_of: asOf, fields, create_only: createOnly }),
  });

// ── Chuyên viên có quyền (mọi đơn vị) ──
export const fetchDay = (kind: Kind, asOf: string) =>
  apiFetch<DayData>(`/api/unit-daily/day?kind=${kind}&as_of=${asOf}`);

export const fetchDailyTimeline = (kind: Kind, range: TimelineRange = { days: 90 }, page = 1) =>
  apiFetch<Timeline>(`/api/unit-daily/timeline?${timelineQuery(kind, range, page)}`);

export const saveDaily = (kind: Kind, company: string, asOf: string, fields: Values, createOnly = false) =>
  apiFetch<{ ok: boolean }>(`/api/unit-daily/report`, {
    method: "PUT", headers: J,
    body: JSON.stringify({ kind, company, as_of: asOf, fields, create_only: createOnly }),
  });

// ── Đổi NGÀY của bản ghi đã nhập (nhập nhầm ngày) ──
/** Nội dung giữ nguyên, chỉ chuyển sang ngày khác. Server ép cửa sổ sửa cho CẢ 2 ngày và từ chối
    (409) nếu ngày mới đã có số liệu. Biểu Thu mua: đơn giá mủ nước/mủ chén được chuyển kèm. */
export type MoveDateResult = { ok: boolean; moved_prices: string[]; kept_prices: string[] };

export const moveDailyDate = (role: Role, kind: Kind, company: string, asOf: string, toDate: string) =>
  apiFetch<MoveDateResult>(
    role === "member" ? "/api/member/daily-report/move-date" : "/api/unit-daily/report/move-date",
    { method: "PUT", headers: J,
      body: JSON.stringify({ kind, company, as_of: asOf, to_date: toDate }) });

// ── Tồn kho ngày trước (nút "Lấy tồn ngày trước") ──
/** Tồn kho là số THỜI ĐIỂM: ngày mới thường gần giống ngày trước → cho chép sang rồi sửa.
    Chỉ trả 3 khối tồn kho, KHÔNG kèm dòng bán (tiêu thụ là số phát sinh trong ngày). */
export type PrevStock = {
  found: boolean;
  as_of?: string;
  stock_not_warehoused?: StockQtyLine[];
  stock_warehoused?: StockQtyLine[];
  stock_material?: number | null;
  stock_ccy?: Ccy;
};

export const fetchPrevStock = (role: Role, company: string, before: string) =>
  apiFetch<PrevStock>(
    `${role === "member" ? "/api/member/daily-report" : "/api/unit-daily"}/prev-stock`
    + `?company=${encodeURIComponent(company)}&before=${before}`);

// ── Tồn kho ĐÃ KÝ HỢP ĐỒNG — bản ghi có vòng đời riêng, KHÔNG nhập lại mỗi ngày ──
/** Hợp đồng nằm trong tồn kho từ `start_date` đến HẾT NGÀY TRƯỚC `delivered_date`
    (chưa giao → còn tồn). Nhập 1 lần; khi xuất kho chỉ cập nhật `delivered_date`. */
export type StockContract = StockSignedLine & {
  id?: number | null;
  company?: string;
  region?: string | null;         // khu vực của đơn vị (chỉ có ở màn tra cứu lịch sử)
  start_date: string;             // ngày bắt đầu tồn kho 'YYYY-MM-DD'
  delivered_date?: string | null; // ngày giao THỰC TẾ (trống = chưa giao)
};

const stockContractBase = (role: Role) =>
  role === "member" ? "/api/member/stock-contracts" : "/api/unit-daily/stock-contracts";

export const fetchStockContracts = (role: Role, asOf?: string, company?: string) =>
  apiFetch<{ as_of: string | null; contracts: StockContract[] }>(
    `${stockContractBase(role)}?${asOf ? `as_of=${asOf}` : ""}`
    + `${company ? `&company=${encodeURIComponent(company)}` : ""}`);

export const saveStockContract = (role: Role, company: string, row: StockContract) =>
  apiFetch<{ contract: StockContract }>(stockContractBase(role), {
    method: "PUT", headers: J, body: JSON.stringify({ ...row, company }),
  });

export const deleteStockContract = (role: Role, id: number) =>
  apiFetch<{ ok: boolean }>(`${stockContractBase(role)}/${id}`, { method: "DELETE" });

// ── Lịch sử TOÀN BỘ hợp đồng đã ký (kể cả đã giao) — màn tra cứu riêng, chỉ xem ──
const stockContractHistoryBase = (role: Role) =>
  role === "member" ? "/api/member/stock-contracts/history" : "/api/unit-daily/contracts/history";

export type ContractStatus = "all" | "undelivered" | "delivered";
export type ContractHistoryFilters = {
  company?: string;      // bỏ qua khi role=member (server tự giới hạn theo đơn vị được gán)
  regions?: string[];    // chỉ role=hq — lọc theo khu vực của đơn vị
  grades?: string[];     // lọc theo chủng loại
  status?: ContractStatus;
  dateFrom?: string;
  dateTo?: string;
  q?: string;
};
export type ContractHistoryData = {
  units: string[]; regions?: string[]; grades?: string[]; contracts: StockContract[];
};

export function fetchStockContractHistory(role: Role, f: ContractHistoryFilters = {}): Promise<ContractHistoryData> {
  const p = new URLSearchParams();
  if (role !== "member" && f.company) p.set("company", f.company);
  if (role !== "member" && f.regions?.length) p.set("regions", f.regions.join(","));
  if (f.grades?.length) p.set("grades", f.grades.join(","));
  if (f.status && f.status !== "all") p.set("status", f.status);
  if (f.dateFrom) p.set("date_from", f.dateFrom);
  if (f.dateTo) p.set("date_to", f.dateTo);
  if (f.q) p.set("q", f.q);
  const qs = p.toString();
  return apiFetch<ContractHistoryData>(`${stockContractHistoryBase(role)}${qs ? `?${qs}` : ""}`);
}

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
  /** Cảnh báo mức kỳ — hiện có: kỳ còn dữ liệu cũ chưa chuyển sang cơ chế hợp đồng. */
  warnings?: string[];
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
