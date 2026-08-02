/* Client Khách hàng + Hợp đồng bán hàng 2 cấp.
   Một bộ endpoint dùng chung cho ĐƠN VỊ THÀNH VIÊN và CHUYÊN VIÊN — server tự ép phạm vi đơn vị
   theo tài khoản, nên frontend không cần tách 2 nhánh /api/member/* như các màn nhập liệu cũ. */

import { API, apiFetch } from "./http";
import { authHeaders } from "./auth-token";

const J = { "Content-Type": "application/json" };

export type Customer = {
  id: number | null;
  company: string;
  code: string | null;
  name: string;
  tax_code: string | null;
  note: string | null;
  is_active: boolean;
};

export type ContractDoc = { file: string; filename: string | null };

export type ContractLine = {
  grade: string;
  qty: number | null;
  qty_dry: number | null;
  price: number | null;
  ccy: string;
  fx: number | null;
  cost: number | null;
};

/** Loại hợp đồng: dài hạn | chuyến. null = chưa khai (bản ghi chuyển từ cơ chế cũ). */
export type ContractType = "long_term" | "spot" | null;

export type Contract = {
  id: number | null;
  company: string;
  parent_id: number | null;
  code: string;
  customer_id: number | null;
  delivery_type: "single" | "multi";
  /** Loại HỢP ĐỒNG (chỉ tiêu báo cáo) — độc lập với loại GIAO ở trên. Chỉ đặt ở hợp đồng mẹ;
   *  phụ lục để null và thừa kế của mẹ khi thống kê. */
  contract_type: ContractType;
  sign_date: string | null;
  expiry_date: string | null;
  /** Ngày MỞ ĐỢT giao — đợt nằm ở "đã ký HĐ chưa giao" từ ngày này đến hết ngày trước ngày giao. */
  start_date: string | null;
  lines: ContractLine[];
  delivered: boolean;
  delivered_at: string | null;
  channel: string | null;
  to_company: string | null;
  payment_date: string | null;
  payment_qty: number | null;
  payment_cost: number | null;
  payment_docs: ContractDoc[];
  files: ContractDoc[];
  note: string | null;
  /* Số suy ra từ `lines`, server trả kèm cho tiện hiển thị. */
  qty: number;
  qty_dry: number;
  cost: number;
  revenue: number | null;
};

export type ContractRow = Contract & {
  delivered_qty: number;
  /** Đã mở đợt nhưng CHƯA điền ngày giao — phần đang nằm trong "đã ký HĐ chưa giao". */
  pending_qty: number;
  remaining_qty: number;
  children: number;
  customer_name?: string | null;
};

export type ContractMeta = {
  units: string[];
  all_units: string[];
  grades: string[];
  dry_required: string[];
  channels: Record<string, string>;
  delivery_types: Record<string, string>;
  contract_types: Record<string, string>;
  /** {đơn vị: đơn vị được nhận hàng nội bộ} — chỉ trong nhóm công ty mẹ–con. Không có tên trong
   *  map = đơn vị đứng một mình → form ẩn hình thức "Tiêu thụ nội bộ". */
  internal_targets: Record<string, string[]>;
  currencies: string[];
  unit_currency: Record<string, string>;   // {đơn vị: nội tệ} — lọc loại tiền cho đúng đơn vị
  customers: Customer[];
};

export type ContractDetail = {
  contract: Contract;
  children: Contract[];
  delivered_qty: number;
  pending_qty: number;
  remaining_qty: number;
};

export type ContractFilters = {
  company?: string;
  customer_id?: number | null;
  status?: "all" | "open" | "done";
  date_from?: string;
  date_to?: string;
  q?: string;
};

/** Tổng hợp tiêu thụ theo đơn vị trong kỳ — TÍNH TỪ các lần giao, không còn ô nhập tay. */
export type ConsumptionSummary = {
  qty: number;
  qty_dry: number;
  cost: number;
  revenue: number | null;
  deliveries: number;
  by_channel: Record<string, number>;
  by_grade: Record<string, number>;
  /** {id khách hàng ("0" = chưa gán): sản lượng + doanh thu} — yêu cầu C1 của khách. */
  by_customer: Record<string, { qty: number; revenue: number }>;
};

/** Báo cáo tiêu thụ: server trả kèm khối 3 cuối kỳ + tên khách để 1 lần gọi là đủ dựng bảng. */
export type ConsumptionReport = {
  date_from: string;
  date_to: string;
  by_company: Record<string, ConsumptionSummary>;
  undelivered: Record<string, UndeliveredSummary>;
  customers: Record<string, string>;
};

/** Đã ký HĐ chưa giao (khối 3) tại một ngày. */
export type UndeliveredSummary = {
  qty: number;
  by_grade: Record<string, number>;
  items: {
    id: number; code: string; remaining: number; qty: number;
    sign_date: string | null; legacy?: boolean;
  }[];
};

// ── Khách hàng ──
export const listCustomers = (includeInactive = true, q = "") =>
  apiFetch<Customer[]>(
    `/api/customers?include_inactive=${includeInactive}${q ? `&q=${encodeURIComponent(q)}` : ""}`);

export const saveCustomer = (body: Partial<Customer> & { company: string; name: string }) =>
  apiFetch<Customer>("/api/customers", { method: "PUT", headers: J, body: JSON.stringify(body) });

export const deleteCustomer = (id: number) =>
  apiFetch<{ ok: boolean }>(`/api/customers/${id}`, { method: "DELETE" });

// ── Hợp đồng ──
export const fetchContractMeta = () => apiFetch<ContractMeta>("/api/sales-contracts/meta");

export function listContracts(f: ContractFilters = {}) {
  const p = new URLSearchParams();
  if (f.company) p.set("company", f.company);
  if (f.customer_id) p.set("customer_id", String(f.customer_id));
  if (f.status && f.status !== "all") p.set("status", f.status);
  if (f.date_from) p.set("date_from", f.date_from);
  if (f.date_to) p.set("date_to", f.date_to);
  if (f.q) p.set("q", f.q);
  const qs = p.toString();
  return apiFetch<{ contracts: ContractRow[] }>(`/api/sales-contracts${qs ? `?${qs}` : ""}`);
}

export const fetchContract = (id: number) =>
  apiFetch<ContractDetail>(`/api/sales-contracts/${id}`);

export const saveContract = (body: Record<string, unknown>) =>
  apiFetch<{ contract: Contract }>("/api/sales-contracts",
    { method: "PUT", headers: J, body: JSON.stringify(body) });

export const deleteContract = (id: number) =>
  apiFetch<{ ok: boolean }>(`/api/sales-contracts/${id}`, { method: "DELETE" });

function consumptionQuery(dateFrom: string, dateTo: string, company?: string, customerId?: number | null) {
  const p = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  if (company) p.set("company", company);
  if (customerId) p.set("customer_id", String(customerId));
  return p.toString();
}

export const fetchConsumption = (dateFrom: string, dateTo: string, company?: string,
                                 customerId?: number | null) =>
  apiFetch<ConsumptionReport>(
    `/api/sales-contracts/consumption?${consumptionQuery(dateFrom, dateTo, company, customerId)}`);

/** Tải Excel Báo cáo tiêu thụ (fetch kèm token → blob, endpoint đòi Bearer). */
export async function downloadConsumptionXlsx(dateFrom: string, dateTo: string, company?: string,
                                              customerId?: number | null): Promise<void> {
  const qs = consumptionQuery(dateFrom, dateTo, company, customerId);
  const res = await fetch(`${API}/api/sales-contracts/consumption.xlsx?${qs}`,
    { headers: authHeaders() });
  if (!res.ok) throw new Error("Không xuất được file Excel.");
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"),
    { href: url, download: `bao-cao-tieu-thu-${dateFrom}-den-${dateTo}.xlsx` });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export const fetchUndelivered = (asOf: string, company?: string) =>
  apiFetch<{ as_of: string; by_company: Record<string, UndeliveredSummary> }>(
    `/api/sales-contracts/undelivered?as_of=${asOf}`
    + (company ? `&company=${encodeURIComponent(company)}` : ""));

/** Upload file đính kèm (hợp đồng scan / chứng từ) — trả tên lưu để gắn vào bản ghi. */
export async function uploadContractFile(file: File): Promise<ContractDoc & { size: number }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/api/sales-contracts/file`,
    { method: "POST", headers: authHeaders(), body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Tải file lên thất bại.");
  }
  return res.json();
}

/** Mở file đính kèm trong tab mới. PHẢI fetch kèm token rồi tạo blob — endpoint đòi Bearer nên
    đặt thẳng vào `<a href>` sẽ luôn 401 (giống `unit-daily-client.openContractFile`). */
export async function openContractFile(doc: ContractDoc): Promise<void> {
  const qs = `?filename=${encodeURIComponent(doc.filename ?? "")}`;
  const res = await fetch(
    `${API}/api/sales-contracts/file/${encodeURIComponent(doc.file)}${qs}`,
    { headers: authHeaders() });
  if (!res.ok) throw new Error("Không tải được file đính kèm.");
  const url = URL.createObjectURL(await res.blob());
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
