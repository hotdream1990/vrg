/* Client CHỐT SỐ LIỆU ĐƠN VỊ (25/08/2026).

   Ban TTKD phát một ĐỢT CHỐT "chốt số liệu đến hết ngày X"; đơn vị rà số rồi XÁC NHẬN, xác nhận
   xong là hết tự sửa ngày ≤ X (chuyên viên/quản trị vẫn sửa hộ được). Quản trị khoá/mở hộ được. */

import { apiFetch } from "./http";

const J = { "Content-Type": "application/json" };

export type LockRound = {
  id: number;
  lock_date: string;
  note: string | null;
  created_at: string | null;
  created_by: string | null;
  cancelled_at: string | null;
  locked?: number;              // số đơn vị đã xác nhận (trả kèm ở danh sách đợt)
};

export type LockUnitState = {
  company: string;
  confirmed: boolean;
  confirmed_at: string | null;
  by_admin: boolean;
  locked_until: string | null;  // mốc chốt HIỆN HÀNH của đơn vị (mọi đợt chưa huỷ)
};

export type LockCurrent = {
  today: string;
  round: LockRound | null;
  units: LockUnitState[];
  /** Mốc khoá của đơn vị ĐÃ SÁP NHẬP vào các đơn vị trên (HĐ đứng tên họ vẫn sửa qua Đề nghị sửa). */
  merged_locked_until?: Record<string, string | null>;
};

/** Số liệu đơn vị sẽ chốt — dùng chung chỉ tiêu với Báo cáo tổng hợp (xem `data_lock_summary`). */
export type LockSummary = {
  round: LockRound;
  company: string;
  lock_date: string;
  date_from: string;
  prev_lock_date: string | null;
  has_purchase_plan: boolean;
  days_entered: { purchase: number; consumption: number };
  purchase: Record<string, number | null>;
  consumption: Record<string, number | null>;
  stock: Record<string, number | string | null>;
  /** Vài ngày thiếu GẦN NHẤT (tối đa 10 mỗi biểu) — tổng số ở `missing_counts`. */
  missing: { purchase: string[]; consumption: string[] };
  missing_counts: { purchase: number; consumption: number };
  /** Mốc bắt đầu rà ngày thiếu của từng biểu (tồn kho có ngoại lệ — xem `STOCK_TRACKED_FROM`). */
  missing_from: { purchase: string; consumption: string };
  missing_total: number;
  /** Đơn vị đã SÁP NHẬP vào đơn vị này — mọi con số ở trên đã GỘP cả họ (như Báo cáo tổng hợp),
   *  và xác nhận chốt là chốt luôn phần của họ. Ảnh chụp cũ (trước 0.4.96) không có khoá này. */
  merged_units?: string[];
};

export type LockStatusRow = {
  company: string;
  region: string | null;
  /** Đơn vị đã SÁP NHẬP vào đơn vị này — không có dòng riêng, được chốt kèm đơn vị nhận. */
  merged_units: { company: string; confirmed: boolean }[];
  /** Đã chốt xong CẢ đơn vị này lẫn các đơn vị đã sáp nhập vào nó. */
  confirmed: boolean;
  confirmed_at: string | null;
  confirmed_by: string | null;
  by_admin: boolean;
  locked_until: string | null;
  snapshot: LockSummary | null;
};

export type LockStatus = {
  round: LockRound | null;
  rows: LockStatusRow[];
  total: number;
  confirmed: number;
};

export const fetchLockCurrent = () => apiFetch<LockCurrent>("/api/data-lock/current");

export const fetchLockSummary = (company: string, roundId?: number) => {
  const p = new URLSearchParams({ company });
  if (roundId) p.set("round_id", String(roundId));
  return apiFetch<LockSummary>(`/api/data-lock/summary?${p}`);
};

export const confirmLock = (roundId: number, company: string) =>
  apiFetch<{ ok: boolean; locked_until: string }>("/api/data-lock/confirm",
    { method: "POST", headers: J, body: JSON.stringify({ round_id: roundId, company }) });

export const fetchLockRounds = (limit = 20) =>
  apiFetch<{ items: LockRound[] }>(`/api/data-lock/rounds?limit=${limit}`);

export const saveLockRound = (body: { id?: number; lock_date: string; note?: string | null }) =>
  apiFetch<{ round: LockRound }>("/api/data-lock/rounds",
    { method: "PUT", headers: J, body: JSON.stringify(body) });

export const cancelLockRound = (id: number, cancelled = true) =>
  apiFetch<{ round: LockRound }>(`/api/data-lock/rounds/${id}/cancel?cancelled=${cancelled}`,
    { method: "POST" });

export const deleteLockRound = (id: number) =>
  apiFetch<{ ok: boolean }>(`/api/data-lock/rounds/${id}`, { method: "DELETE" });

export const fetchLockStatus = (opt: { round_id?: number; only_pending?: boolean; q?: string } = {}) => {
  const p = new URLSearchParams();
  if (opt.round_id) p.set("round_id", String(opt.round_id));
  if (opt.only_pending) p.set("only_pending", "true");
  if (opt.q) p.set("q", opt.q);
  return apiFetch<LockStatus>(`/api/data-lock/status?${p}`);
};

export const lockUnits = (roundId: number, companies: string[]) =>
  apiFetch<{ ok: boolean; count: number }>("/api/data-lock/lock",
    { method: "POST", headers: J, body: JSON.stringify({ round_id: roundId, companies }) });

export const unlockUnits = (roundId: number, companies: string[]) =>
  apiFetch<{ ok: boolean; count: number }>("/api/data-lock/unlock",
    { method: "POST", headers: J, body: JSON.stringify({ round_id: roundId, companies }) });
