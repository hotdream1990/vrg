/* Client API Nhu cầu thị trường (free text theo đơn vị / ngày).
   - Đơn vị thành viên: `/api/member/market-demand` (server ép company ∈ đơn vị được gán).
   - Chuyên viên có quyền `market_demand`: `/api/market-demand` (xem/sửa mọi đơn vị). */

import { apiFetch } from "./http";

export type MarketDemand = {
  units: string[];                    // đơn vị (member: được gán · editor: tất cả active)
  today: string;                      // YYYY-MM-DD (giờ VN)
  edit_window_days: number;           // sửa được: hôm nay + N ngày gần nhất
  entries: Record<string, string>;    // {đơn vị: nội dung nhu cầu} cho ngày đang xem
};

const J = { "Content-Type": "application/json" };

// ── Đơn vị thành viên (chỉ đơn vị được gán) ──
export const fetchMyDemand = (as_of: string) =>
  apiFetch<MarketDemand>(`/api/member/market-demand?as_of=${as_of}`);

export const saveMyDemand = (company: string, as_of: string, content: string, createOnly = false) =>
  apiFetch<{ ok: boolean }>(`/api/member/market-demand`,
    { method: "PUT", headers: J, body: JSON.stringify({ company, as_of, content, create_only: createOnly }) });

// ── Chuyên viên có quyền (mọi đơn vị) ──
export const fetchAllDemand = (as_of: string) =>
  apiFetch<MarketDemand>(`/api/market-demand?as_of=${as_of}`);

// createOnly=true (nút Thêm nhu cầu) → server chặn 409 nếu (ngày, đơn vị) đã có nhu cầu.
export const saveDemand = (company: string, as_of: string, content: string, createOnly = false) =>
  apiFetch<{ ok: boolean }>(`/api/market-demand`,
    { method: "PUT", headers: J, body: JSON.stringify({ company, as_of, content, create_only: createOnly }) });

// Timeline tổng quát cho chuyên viên: chỉ các ngày ĐÃ có nhu cầu (ẩn ngày trống).
export type DemandEntry = {
  as_of: string; company: string; content: string; updated_by: string | null; updated_at: string;
};
export type DemandTimeline = {
  today: string; edit_window_days: number; units: string[]; entries: DemandEntry[];
};

export const fetchDemandTimeline = (days = 90) =>
  apiFetch<DemandTimeline>(`/api/market-demand/timeline?days=${days}`);

// Đơn vị thành viên: timeline chỉ các đơn vị được gán (đa đơn vị/1 tài khoản).
export const fetchMyDemandTimeline = (days = 90) =>
  apiFetch<DemandTimeline>(`/api/member/market-demand/timeline?days=${days}`);
