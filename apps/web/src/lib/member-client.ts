/* Client API cho tài khoản ĐƠN VỊ THÀNH VIÊN — tự xem/nhập giá mủ nước + mủ chén của CÁC đơn vị được gán.
   Backend scope theo token (get_current_member): mỗi thao tác ghi kèm `company` và server kiểm tra
   company thuộc danh sách gán của tài khoản. */

import { apiFetch } from "./http";

/** Khớp `market_meta.PURCHASE_PRICE_TYPES` ở backend (mủ nước · mủ chén · mủ dây). */
export type MemberPriceType = "purchase" | "purchase_cup" | "purchase_lace";

export type UnitSheet = {
  purchase: Record<string, number>;       // {date: giá mủ nước (đồng/độ TSC)}
  purchase_cup: Record<string, number>;   // {date: giá mủ chén (đồng/độ DRC)}
  purchase_lace: Record<string, number>;  // {date: giá mủ dây (đồng/độ DRC)}
  dates: string[];                        // ngày có dữ liệu (mới → cũ)
};

export type MemberPrices = {
  units: string[];                       // các đơn vị được gán + đơn vị đã sáp nhập vào (chỉ xem)
  view_only_units?: string[];            // phần CHỈ XEM trong `units` (đơn vị đã sáp nhập)
  today: string;                         // YYYY-MM-DD (giờ VN, để tính cửa sổ sửa)
  edit_window_days: number;              // sửa được: hôm nay + N ngày gần nhất
  sheets: Record<string, UnitSheet>;     // {đơn vị: lịch sử giá}
};

const J = { "Content-Type": "application/json" };

/** Lịch sử giá mủ nước + mủ chén của tất cả đơn vị được gán. */
export const fetchMyPrices = (days = 30) =>
  apiFetch<MemberPrices>(`/api/member/prices?days=${days}`);

/** Nhập/sửa 1 ô giá cho 1 đơn vị được gán, ngày trong cửa sổ cho phép.
    `basis` (chỉ mủ chén) = tsc|drc — đổi nhãn đơn vị lưu kèm giá. */
export const upsertMyPrice = (company: string, as_of: string, price_type: MemberPriceType,
                              price: number) =>
  apiFetch<{ ok: boolean }>(`/api/member/prices`,
    { method: "PUT", headers: J, body: JSON.stringify({ company, as_of, price_type, price }) });

/** Xoá 1 ô giá của 1 đơn vị được gán. */
export const clearMyPrice = (company: string, as_of: string, price_type: MemberPriceType) =>
  apiFetch<{ deleted: boolean }>(
    `/api/member/prices?company=${encodeURIComponent(company)}&as_of=${as_of}&price_type=${price_type}`,
    { method: "DELETE" });

// ── Đơn vị còn thiếu gì (bảng nhắc hiện trên mọi màn) ──
export type PendingBatch = {
  id: number;
  code: string;             // số đợt giao
  contract_code: string;    // số hợp đồng cha
  qty: number;              // sản lượng đang treo (tấn)
  since: string;            // lần ghi gần nhất của đợt
  days: number;             // đã treo bao nhiêu ngày
};

/** Lần giao bán ngoại tệ mà bỏ trống tỷ giá — doanh thu lần đó chưa được tính vào báo cáo. */
export type MissingFxDelivery = {
  id: number;
  code: string;             // số đợt giao
  contract_code: string;    // số hợp đồng cha
  delivered_at: string;     // ngày giao
  qty: number;              // sản lượng của các dòng thiếu tỷ giá (tấn)
  ccy: string;              // loại tiền đang khai (USD…)
  editable: boolean;        // ngoài cửa sổ sửa thì đơn vị không tự điền được
};

/** Một ô số liệu ĐÃ LƯU nhưng nhiều khả năng nhầm đơn vị tính / thiếu tỷ giá (server rà lại bằng
 *  đúng bộ biên của form — xem `entry-bounds.ts` ↔ `app/core/entry_bounds.py`). */
export type DataCheck = {
  as_of: string;                    // ngày của phiếu / lần giao
  kind: "purchase" | "stock" | "contract";   // mở màn nào để sửa
  where: string;                    // chỉ đường tới ô: bảng · dòng · cột
  message: string;                  // lý do, y hệt câu hiện trong form
  code: string | null;              // số hợp đồng/đợt giao (chỉ với kind = contract)
  editable: boolean;                // ngoài cửa sổ sửa thì đơn vị không tự sửa được
};

export type UnitChecklist = {
  company: string;
  needs_purchase: boolean;      // đơn vị có kế hoạch thu mua → mới phải nộp biểu Thu mua
  purchase_missing: string[];   // ngày chưa nhập (mới → cũ)
  stock_missing: string[];
  year_plan_missing: boolean;
  year: number;
  pending_batches: PendingBatch[];
  /** Hợp đồng đã chốt hoàn thành mà chưa ghi lần giao nào — sản lượng không vào tiêu thụ. */
  completed_no_delivery: { id: number; code: string; qty: number; completed_at: string }[];
  missing_fx: MissingFxDelivery[];  // rà từ 01/01 năm nay, KHÔNG giới hạn trong alert_days
  data_checks: DataCheck[];         // ô cần soát lại — cũng rà từ 01/01 năm nay
};

export type MemberChecklist = {
  today: string;
  alert_days: number;           // rà bao nhiêu ngày gần nhất (admin cấu hình)
  enabled: boolean;             // admin đặt 0 ngày = tắt hẳn cảnh báo
  editable_from: string;        // ngày cũ hơn mốc này đơn vị KHÔNG tự sửa được nữa
  days: string[];               // các ngày được rà (mới → cũ)
  units: UnitChecklist[];
  total_missing: number;
};

/** Việc còn thiếu của các đơn vị được gán — chỉ tính phần CÒN SỬA ĐƯỢC. */
export const fetchMyChecklist = () => apiFetch<MemberChecklist>("/api/member/checklist");
