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

export type Contract = {
  id: number | null;
  company: string;
  parent_id: number | null;
  code: string;
  customer_id: number | null;
  delivery_type: "single" | "multi";
  sign_date: string | null;
  expiry_date: string | null;
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
  currencies: string[];
  customers: Customer[];
};

export type ContractDetail = {
  contract: Contract;
  children: Contract[];
  delivered_qty: number;
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

export const fetchConsumption = (dateFrom: string, dateTo: string, company?: string) =>
  apiFetch<{ date_from: string; date_to: string; by_company: Record<string, ConsumptionSummary> }>(
    `/api/sales-contracts/consumption?date_from=${dateFrom}&date_to=${dateTo}`
    + (company ? `&company=${encodeURIComponent(company)}` : ""));

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
