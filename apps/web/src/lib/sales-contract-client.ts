/* Client Khách hàng + Hợp đồng bán hàng 2 cấp.
   Một bộ endpoint dùng chung cho ĐƠN VỊ THÀNH VIÊN và CHUYÊN VIÊN — server tự ép phạm vi đơn vị
   theo tài khoản, nên frontend không cần tách 2 nhánh /api/member/* như các màn nhập liệu cũ. */

import { API, apiFetch } from "./http";
import { authHeaders } from "./auth-token";
import type { MasterContract } from "./master-contract-client";

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

/** Trần sản lượng thực giao so với hợp đồng đã ký (110%). Thực tế cân hàng lệch quanh 5% nên
 *  chặn đúng 100% là chặn nghiệp vụ thật. PHẢI khớp `sales_contract_repo.MAX_OVER_RATIO` ở server
 *  — lệch nhau thì form cho lưu mà server trả lỗi (hoặc ngược lại, chặn oan). */
export const MAX_OVER_RATIO = 1.1;

export type ContractLine = {
  grade: string;
  qty: number | null;
  qty_dry: number | null;
  price: number | null;
  ccy: string;
  fx: number | null;
  /** "Hiệu lực từ" (YYYY-MM-DD) — CHỈ dòng của hợp đồng, đợt giao không có. null/không có khoá =
   *  theo ngày ký. Dùng khi TĂNG sản lượng sau khi ký: dòng tăng thêm chỉ vào "đã ký HĐ chưa giao"
   *  từ ngày này. Server lưu null khi trùng ngày ký. */
  from_date?: string | null;
};

/** Loại hợp đồng: dài hạn | chuyến. null = chưa khai (bản ghi chuyển từ cơ chế cũ). */
export type ContractType = "long_term" | "spot" | null;

export type Contract = {
  id: number | null;
  company: string;
  parent_id: number | null;
  /** Khác null = hợp đồng này nằm trong một HỒ SƠ HỢP ĐỒNG MẸ (HĐNT/HĐDH). CHỈ là liên kết —
   *  hợp đồng vẫn giữ khách hàng, loại hợp đồng và mọi số liệu của chính nó. */
  master_id: number | null;
  code: string;
  customer_id: number | null;
  delivery_type: "single" | "multi";
  /** Loại HỢP ĐỒNG (chỉ tiêu báo cáo) — độc lập với loại GIAO ở trên. Chỉ đặt ở hợp đồng;
   *  đợt giao để null và thừa kế của hợp đồng khi thống kê. */
  contract_type: ContractType;
  sign_date: string | null;
  expiry_date: string | null;
  /** Ngày mở đợt — ô đã BỎ khỏi form (05/08/2026), chỉ còn giữ dữ liệu cũ. */
  start_date: string | null;
  lines: ContractLine[];
  delivered: boolean;
  delivered_at: string | null;
  channel: string | null;
  to_company: string | null;
  /** NGUỒN TIÊU THỤ của lần giao: `exploit` khai thác · `purchase` thu mua (03/10/2026). Bắt buộc
   *  khi có ngày giao; hợp đồng giao nhiều lần để null (khai ở từng đợt giao). */
  source: string | null;
  /** Hoá đơn của ĐỢT GIAO: số hoá đơn + danh sách file scan. */
  invoice_no: string | null;
  invoice_docs: ContractDoc[];
  payment_date: string | null;
  payment_qty: number | null;
  payment_docs: ContractDoc[];
  files: ContractDoc[];
  note: string | null;
  /** Ngày HOÀN THÀNH hợp đồng — null = đang thực hiện (còn nằm ở "đã ký HĐ chưa giao"). */
  completed_at: string | null;
  /* Số suy ra từ `lines`, server trả kèm cho tiện hiển thị. */
  qty: number;
  qty_dry: number;
  /** Thành tiền quy về ĐỒNG. null = có dòng ngoại tệ thiếu tỷ giá (KHÔNG phải 0). */
  revenue: number | null;
  /** Hàng có chứng chỉ (PEFC · EUDR · VRG GREEN) + khoản premium khách trả thêm. Khai ở NGỌN:
   *  hợp đồng giao 1 lần khai trên chính nó, giao nhiều lần thì ở TỪNG ĐỢT GIAO (27/08/2026). */
  certs?: string[];
  premium?: number | null;
  premium_ccy?: string | null;
};

export type ContractRow = Contract & {
  delivered_qty: number;
  /** Đã lập đợt nhưng CHƯA điền ngày giao — phần này NẰM TRONG `remaining_qty`. */
  pending_qty: number;
  /** Còn phải giao = sản lượng hợp đồng − đã giao (SL CHƯA QUY KHÔ — số ghi trên hợp đồng). */
  remaining_qty: number;
  /** Còn phải giao theo gốc số của báo cáo & bảng chốt số liệu (latex/mủ NL = QUY KHÔ) — khác
   *  `remaining_qty` chỉ ở hợp đồng có dòng quy khô. */
  remaining_dry_qty: number;
  /** Phần giao VƯỢT sản lượng hợp đồng (thực giao được lệch, trần 110%). */
  over_qty: number;
  /** Thành tiền của HÀNG ĐÃ GIAO, quy về ĐỒNG — khác `revenue` (tiền ghi trên hợp đồng) vì sản
   *  lượng/đơn giá chốt lại ở từng đợt giao. null = có đợt thiếu tỷ giá (KHÔNG phải 0). */
  delivered_revenue: number | null;
  /** Các HÌNH THỨC TIÊU THỤ có trong hợp đồng (của chính nó + các đợt giao); rỗng = chưa khai. */
  channels: string[];
  children: number;
  customer_name?: string | null;
  /** Số hợp đồng mẹ (nếu là phụ lục) — server tra sẵn để bảng khỏi gọi thêm. */
  master_code?: string | null;
};

export type ContractMeta = {
  units: string[];
  all_units: string[];
  /** Đơn vị ĐÃ SÁP NHẬP — chỉ để LỌC hợp đồng cũ của họ, không mở hợp đồng mới ở đó nữa. */
  merged_units?: string[];
  grades: string[];
  dry_required: string[];
  /** Danh mục chứng chỉ của lô hàng + loại tiền của premium (26/08/2026). */
  certs?: string[];
  premium_currencies?: string[];
  channels: Record<string, string>;
  /** Nguồn tiêu thụ: {exploit: "Khai thác", purchase: "Thu mua"}. */
  sources: Record<string, string>;
  delivery_types: Record<string, string>;
  contract_types: Record<string, string>;
  /** Ô vẫn sửa được sau khi đơn vị đã CHỐT số liệu (server quyết, xem `sales_contract_lock.py`). */
  editable_when_locked: { key: string; label: string }[];
  /** Nhãn loại HỢP ĐỒNG MẸ: principle = HĐ nguyên tắc · long_term = HĐ dài hạn. */
  master_types: Record<string, string>;
  /** {đơn vị: đơn vị được nhận hàng nội bộ} — chỉ trong nhóm công ty mẹ–con. Không có tên trong
   *  map = đơn vị đứng một mình → form ẩn hình thức "Tiêu thụ nội bộ". */
  internal_targets: Record<string, string[]>;
  currencies: string[];
  unit_currency: Record<string, string>;   // {đơn vị: nội tệ} — lọc loại tiền cho đúng đơn vị
  /* KHÔNG có danh mục khách hàng: mỗi đơn vị một danh mục riêng nên tổng số khách tăng theo số
     đơn vị → dùng <CustomerPicker> (tìm ở server) thay vì tải cả danh mục về máy. */
};

export type ContractDetail = {
  contract: Contract;
  /** Các ĐỢT GIAO của hợp đồng (rỗng với hợp đồng giao 1 lần). */
  children: Contract[];
  delivered_qty: number;
  pending_qty: number;
  remaining_qty: number;
  over_qty: number;
  /** Thành tiền của HÀNG ĐÃ GIAO (đồng) — xem `ContractRow.delivered_revenue`. */
  delivered_revenue: number | null;
  /** Trần sản lượng được phép giao (110% sản lượng hợp đồng). */
  max_qty: number;
  customer_name: string | null;
  /** Hợp đồng mẹ của phụ lục (null = hợp đồng đứng một mình). Giá của phụ lục vốn tính theo
   *  CÔNG THỨC GIÁ ghi ở hợp đồng mẹ nên màn chi tiết phải hiện được nó. */
  master: MasterContract | null;
};

export type ContractFilters = {
  company?: string;
  /** Lọc theo MỘT HOẶC NHIỀU khách hàng (rỗng = tất cả). */
  customer_ids?: number[];
  status?: "all" | "open" | "done" | "completed";
  /** Lọc hình thức tiêu thụ; chuỗi rỗng = hợp đồng chưa khai hình thức. */
  channels?: string[];
  date_from?: string;
  date_to?: string;
  q?: string;
  /** Chỉ phụ lục của MỘT hợp đồng mẹ (xem trọn một hồ sơ ngay ở màn danh sách). */
  master_id?: number;
  /** Chỉ hợp đồng CHƯA gắn hợp đồng mẹ — ô chọn phụ lục ở màn Hợp đồng mẹ, và bộ lọc "chưa gắn
   *  hồ sơ" ở màn danh sách (để rà những hợp đồng cần đưa vào hồ sơ). */
  unlinked?: boolean;
  /** Phân trang Ở SERVER — danh sách hợp đồng dài thêm mỗi ngày, không tải hết về máy. */
  page?: number;
  page_size?: number;
};

/** Dòng TỔNG CỘNG — cộng TOÀN BỘ hợp đồng khớp bộ lọc, KHÔNG phải trang đang xem.
 *  `*_missing` = số hợp đồng không quy đổi được tiền (thiếu đơn giá / tỷ giá) nên chưa vào tổng. */
export type ContractTotals = {
  qty: number;
  delivered_qty: number;
  pending_qty: number;
  remaining_qty: number;
  /** Như `remaining_qty` nhưng theo gốc QUY KHÔ — khớp "Đã ký HĐ chưa giao" ở bảng chốt số liệu. */
  remaining_dry_qty: number;
  over_qty: number;
  children: number;
  revenue: number;
  revenue_missing: number;
  delivered_revenue: number;
  delivered_revenue_missing: number;
};

export type ContractPage = {
  contracts: ContractRow[]; total: number; totals: ContractTotals;
  page: number; page_size: number;
};

/** Tổng hợp tiêu thụ theo đơn vị trong kỳ — TÍNH TỪ các lần giao, không còn ô nhập tay. */
export type ConsumptionSummary = {
  /** Sản lượng tiêu thụ — đã là QUY KHÔ với latex/mủ nguyên liệu (PA1). */
  qty: number;
  qty_dry: number;
  /** SL chưa quy khô của riêng các dòng CÓ quy khô — số cân thực tế, không lặp lại `qty`. */
  qty_wet: number;
  revenue: number | null;
  deliveries: number;
  by_channel: Record<string, number>;
  /** Sản lượng theo nguồn tiêu thụ: exploit (khai thác) · purchase (thu mua). */
  by_source?: Record<string, number>;
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
  /** Sản lượng CÒN PHẢI GIAO theo đơn vị tại `backlog_as_of` (= ngày cuối kỳ). Vắng = API cũ. */
  backlog?: Record<string, Backlog>;
  backlog_as_of?: string;
};

/** 1 hợp đồng mẹ CÓ sản lượng cam kết — tiến độ giao lũy kế từ ngày ký (tấn, gốc quy khô). */
export type BacklogItem = {
  id: number; code: string; master_type: "long_term" | "principle"; customer_id: number | null;
  sign_date: string | null; expiry_date: string | null;
  committed: number; delivered: number; remaining: number; pct: number | null; expired: boolean;
  expired_short?: number;   // HĐ mẹ hết hạn: cam kết chưa ký phụ lục — không còn phải giao
  after_year?: boolean;     // còn hiệu lực sau 31/12 (hoặc không thời hạn)
};

/** Còn phải giao của 1 đơn vị (plans/260926-hd-dai-han-phai-giao/api-contract.md). Hợp đồng thuộc
 *  HĐ mẹ có cam kết tính ở cấp HĐ mẹ; còn lại tính theo loại của chính nó — không đếm trùng. */
export type Backlog = {
  spot_undelivered: number;         // HĐ chuyến đã ký chưa giao
  principle_undelivered: number;    // HĐ nguyên tắc (phụ lục HĐNT) đã ký chưa giao
  lt_unlinked_undelivered: number;  // phụ lục dài hạn ngoài HĐDH có cam kết: đã ký chưa giao
  unknown_undelivered: number;      // hợp đồng chưa khai loại
  master_committed: number;
  master_delivered: number;
  master_remaining: number;         // HĐ mẹ còn hiệu lực + phụ lục đã ký chưa giao của HĐ mẹ hết hạn
  master_expired_short: number;     // HĐ mẹ hết hạn: cam kết chưa ký phụ lục — KHÔNG vào phải giao
  master_remaining_after_year?: number;  // phần còn lại thuộc HĐ mẹ hiệu lực sau 31/12
  masters: number;
  master_pct: number | null;
  lt_remaining: number;             // = master_remaining + lt_unlinked_undelivered
  to_deliver: number;               // = spot + principle + lt_remaining + unknown
  items: BacklogItem[];
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
export type CustomerPage = { items: Customer[]; total: number; page: number; page_size: number };

/** MỘT TRANG khách hàng — tìm kiếm và cắt trang đều ở server (danh mục của cả Tập đoàn rất dài). */
export function listCustomers(
  opt: { q?: string; page?: number; pageSize?: number; includeInactive?: boolean } = {},
) {
  const p = new URLSearchParams();
  p.set("include_inactive", String(opt.includeInactive ?? true));
  if (opt.q) p.set("q", opt.q);
  p.set("page", String(opt.page ?? 1));
  p.set("page_size", String(opt.pageSize ?? 50));
  return apiFetch<CustomerPage>(`/api/customers?${p}`);
}

/** Tìm khách hàng Ở SERVER cho ô chọn khách (danh mục riêng từng đơn vị nên rất dài).
 *  Phạm vi đơn vị do server ép theo tài khoản; `company` chỉ thu hẹp thêm trong phạm vi đó.
 *  `ids` dùng để tra lại TÊN của các khách đang được chọn khi chúng không nằm trong kết quả tìm. */
export function searchCustomers(
  opt: { q?: string; company?: string; ids?: number[]; limit?: number; includeInactive?: boolean },
) {
  const p = new URLSearchParams();
  if (opt.q) p.set("q", opt.q);
  if (opt.company) p.set("company", opt.company);
  if (opt.limit) p.set("limit", String(opt.limit));
  p.set("include_inactive", String(opt.includeInactive ?? false));
  (opt.ids ?? []).forEach((id) => p.append("ids", String(id)));
  return apiFetch<CustomerPage>(`/api/customers?${p}`).then((r) => r.items);
}

export const saveCustomer = (body: Partial<Customer> & { company: string; name: string }) =>
  apiFetch<Customer>("/api/customers", { method: "PUT", headers: J, body: JSON.stringify(body) });

export const deleteCustomer = (id: number) =>
  apiFetch<{ ok: boolean }>(`/api/customers/${id}`, { method: "DELETE" });

// ── Hợp đồng ──
export const fetchContractMeta = () => apiFetch<ContractMeta>("/api/sales-contracts/meta");

export function listContracts(f: ContractFilters = {}) {
  const p = new URLSearchParams();
  if (f.company) p.set("company", f.company);
  // Lọc nhiều khách = lặp lại tham số (`customer_id=1&customer_id=2`) — FastAPI gom thành list.
  (f.customer_ids ?? []).forEach((id) => p.append("customer_id", String(id)));
  if (f.status && f.status !== "all") p.set("status", f.status);
  (f.channels ?? []).forEach((c) => p.append("channel", c));
  if (f.date_from) p.set("date_from", f.date_from);
  if (f.date_to) p.set("date_to", f.date_to);
  if (f.q) p.set("q", f.q);
  if (f.master_id) p.set("master_id", String(f.master_id));
  if (f.unlinked) p.set("unlinked", "true");
  p.set("page", String(f.page ?? 1));
  p.set("page_size", String(f.page_size ?? 25));
  return apiFetch<ContractPage>(`/api/sales-contracts?${p}`);
}

export const fetchContract = (id: number) =>
  apiFetch<ContractDetail>(`/api/sales-contracts/${id}`);

export const saveContract = (body: Record<string, unknown>) =>
  apiFetch<{ contract: Contract }>("/api/sales-contracts",
    { method: "PUT", headers: J, body: JSON.stringify(body) });

export const deleteContract = (id: number) =>
  apiFetch<{ ok: boolean }>(`/api/sales-contracts/${id}`, { method: "DELETE" });

/** Chốt HOÀN THÀNH hợp đồng (`completedAt = null` là mở lại) — phần chênh còn lại rời khỏi
 *  "đã ký HĐ chưa giao" kể từ ngày chốt. */
/** Chốt hoàn thành. Hợp đồng GIAO 1 LẦN chưa có ngày giao thì chốt CHÍNH LÀ ghi nhận đã giao —
 *  gửi kèm `channel` + `source` (+ `delivered_at`, `to_company`), hoặc `no_delivery` nếu hợp đồng huỷ. */
export const setContractCompletion = (
  id: number, completedAt: string | null,
  delivery?: { delivered_at?: string | null; channel?: string | null;
               to_company?: string | null; source?: string | null; no_delivery?: boolean },
) =>
  apiFetch<{ contract: Contract }>(`/api/sales-contracts/${id}/completion`,
    { method: "PUT", headers: J,
      body: JSON.stringify({ completed_at: completedAt, ...(delivery ?? {}) }) });

/** Chuyển giao-1-lần ↔ giao-nhiều-lần tại chỗ; lần giao đang có được dời thành đợt giao đầu tiên. */
export const setContractDeliveryType = (id: number, deliveryType: "single" | "multi") =>
  apiFetch<{ contract: Contract }>(`/api/sales-contracts/${id}/delivery-type`,
    { method: "PUT", headers: J, body: JSON.stringify({ delivery_type: deliveryType }) });

function consumptionQuery(dateFrom: string, dateTo: string, company?: string,
                          customerIds?: number[], grades?: string[]) {
  const p = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  if (company) p.set("company", company);
  (customerIds ?? []).forEach((id) => p.append("customer_id", String(id)));
  (grades ?? []).forEach((g) => p.append("grade", g));
  return p.toString();
}

export const fetchConsumption = (dateFrom: string, dateTo: string, company?: string,
                                 customerIds?: number[], grades?: string[]) =>
  apiFetch<ConsumptionReport>(
    `/api/sales-contracts/consumption?${consumptionQuery(dateFrom, dateTo, company, customerIds, grades)}`);

/** Một lần giao trong bảng "Lịch sử đợt giao" — nhãn loại HĐ/hình thức đã dịch sẵn ở server. */
export type DeliveryHistoryRow = {
  id: number;
  delivered_at: string | null;
  company: string;
  contract_code: string | null;
  batch_code: string | null;      // null = hợp đồng giao trọn 1 lần, không phải đợt
  customer_name: string | null;
  contract_type: string | null;
  /** Nhóm báo cáo theo hồ sơ mẹ: HĐ chuyến · HĐ nguyên tắc · HĐ dài hạn (null = chưa khai loại). */
  contract_group: string | null;
  channel: string | null;
  /** Nhãn nguồn tiêu thụ (Khai thác · Thu mua). */
  source?: string | null;
  grades: string;
  qty: number;                    // đã là QUY KHÔ với latex/mủ nguyên liệu (PA1)
  qty_dry: number;
  qty_wet: number;                // SL chưa quy khô của riêng các dòng có quy khô
  revenue: number | null;         // null = thiếu tỷ giá, KHÔNG phải bằng 0
  invoice_no: string | null;
};

export type DeliveryHistory = {
  rows: DeliveryHistoryRow[];
  total: number;
  /** Lũy kế CẢ KỲ (mọi trang) — server cộng, không phải tổng của trang đang xem. */
  totals: { qty: number; qty_dry: number; qty_wet: number; revenue: number | null };
  page: number;
  page_size: number;
};

/** Lịch sử từng lần giao — phân trang ở SERVER (prod đã hơn 3.000 lần giao). */
export const fetchConsumptionDeliveries = (
  dateFrom: string, dateTo: string, company: string | undefined,
  customerIds: number[] | undefined, grades: string[] | undefined,
  page: number, pageSize: number,
) => {
  const qs = consumptionQuery(dateFrom, dateTo, company, customerIds, grades);
  return apiFetch<DeliveryHistory>(
    `/api/sales-contracts/consumption/deliveries?${qs}&page=${page}&page_size=${pageSize}`);
};

/** Tải Excel Báo cáo tiêu thụ (fetch kèm token → blob, endpoint đòi Bearer). */
export async function downloadConsumptionXlsx(dateFrom: string, dateTo: string, company?: string,
                                              customerIds?: number[], grades?: string[]): Promise<void> {
  const qs = consumptionQuery(dateFrom, dateTo, company, customerIds, grades);
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
