/* Client HỢP ĐỒNG MẸ — HĐ nguyên tắc (HĐNT) / HĐ dài hạn (HĐDH).

   Hợp đồng mẹ là HỒ SƠ GỐC ký với khách hàng (khách hàng · cam kết chủng loại–số lượng ·
   công thức giá · bản scan). Từng chuyến hàng vẫn nhập ở màn Hợp đồng như cũ; chọn hợp đồng mẹ chỉ
   để NỐI bản ghi vào hồ sơ — không đổi khách hàng hay số liệu nào của hợp đồng.

   ⚠ Hợp đồng mẹ KHÔNG có số liệu tiêu thụ — mọi báo cáo sản lượng vẫn đọc từ hợp đồng/đợt giao. */

import { apiFetch } from "./http";
import type { Contract, ContractDoc } from "./sales-contract-client";

const J = { "Content-Type": "application/json" };

export type MasterType = "principle" | "long_term";

/** 1 dòng cam kết: chủng loại · số lượng · quy khô. KHÔNG có đơn giá/loại tiền/tỷ giá — giá là số
 *  của từng chuyến (khai ở phụ lục) hoặc đi theo công thức giá của hồ sơ (chốt 25/08/2026).
 *  Số lượng để trống được: HĐ nguyên tắc thường chỉ chốt chủng loại. */
export type MasterLine = {
  grade: string;
  qty: number | null;                   // latex/mủ nguyên liệu: SL MỦ NƯỚC (tấn)
  qty_dry: number | null;               // quy khô (tấn) — chỉ latex và mủ nguyên liệu
};

export type MasterContract = {
  id: number | null;
  company: string;
  code: string;                   // SỐ HỢP ĐỒNG (mẹ)
  master_type: MasterType;
  customer_id: number | null;
  sign_date: string | null;
  expiry_date: string | null;
  lines: MasterLine[];
  /** Công thức giá — TEXT tự do (vd "SICOM TSR20 bình quân tuần trước + 30 USD/tấn"). */
  price_formula: string | null;
  files: ContractDoc[];
  note: string | null;
  /* Server trả kèm cho tiện hiển thị. */
  qty: number;                    // tổng số lượng cam kết trên hợp đồng mẹ
  customer_name?: string | null;
  annexes?: number;               // số PHỤ LỤC đã nối về
  annex_qty?: number;             // tổng sản lượng đã ký ở các phụ lục
};

export type MasterPage = {
  items: MasterContract[];
  total: number;
  page: number;
  page_size: number;
  master_types: Record<string, string>;
};

export type MasterDetail = {
  master: MasterContract;
  /** Các PHỤ LỤC đã nối về hợp đồng mẹ (không gồm đợt giao bên trong từng phụ lục). */
  annexes: Contract[];
  annex_qty: number;
};

export type MasterFilters = {
  company?: string;
  q?: string;
  master_type?: MasterType | "";
  page?: number;
  page_size?: number;
};

export function listMasterContracts(f: MasterFilters = {}) {
  const p = new URLSearchParams();
  if (f.company) p.set("company", f.company);
  if (f.q) p.set("q", f.q);
  if (f.master_type) p.set("master_type", f.master_type);
  p.set("page", String(f.page ?? 1));
  p.set("page_size", String(f.page_size ?? 25));
  return apiFetch<MasterPage>(`/api/master-contracts?${p}`);
}

/** Tìm hợp đồng mẹ Ở SERVER cho ô chọn (mỗi đơn vị một bộ hồ sơ nên danh sách dài dần).
 *  `ids` để tra lại nhãn của hợp đồng mẹ đang chọn khi nó không nằm trong kết quả tìm. */
export function searchMasterContracts(
  opt: { q?: string; company?: string; ids?: number[]; limit?: number },
) {
  const p = new URLSearchParams();
  if (opt.q) p.set("q", opt.q);
  if (opt.company) p.set("company", opt.company);
  p.set("limit", String(opt.limit ?? 50));
  (opt.ids ?? []).forEach((id) => p.append("ids", String(id)));
  return apiFetch<MasterPage>(`/api/master-contracts?${p}`).then((r) => r.items);
}

export const fetchMasterContract = (id: number) =>
  apiFetch<MasterDetail>(`/api/master-contracts/${id}`);

export const saveMasterContract = (body: Record<string, unknown>) =>
  apiFetch<{ master: MasterContract }>("/api/master-contracts",
    { method: "PUT", headers: J, body: JSON.stringify(body) });

export const deleteMasterContract = (id: number) =>
  apiFetch<{ ok: boolean }>(`/api/master-contracts/${id}`, { method: "DELETE" });

/** GẮN các hợp đồng ĐÃ CÓ vào hợp đồng mẹ (`attach = false` là GỠ ra).
 *  Gắn/gỡ CHỈ đổi liên kết — không đụng khách hàng hay số liệu nào của hợp đồng. */
export const linkMasterAnnexes = (masterId: number, contractIds: number[], attach = true) =>
  apiFetch<{ count: number; attached: boolean; annexes: Contract[] }>(
    `/api/master-contracts/${masterId}/annexes`,
    { method: "PUT", headers: J, body: JSON.stringify({ contract_ids: contractIds, attach }) });
