/* Client API Lịch sử hỏi đáp Trợ lý AI — xem lại log hội thoại cũ + dọn log cho nhẹ.
   Gác bằng cap `assistant`; CHỈ admin xoá được và lọc được theo người dùng (backend chặn). */

import { apiFetch } from "./http";

const BASE = "/api/assistant/history";

/** Một phiên hỏi đáp (gộp nhiều lượt của cùng `session_id`). */
export type HistorySession = {
  session_id: string;
  username: string;
  first_at: string;   // ISO datetime — lượt hỏi đầu tiên
  last_at: string;    // ISO datetime — lượt hỏi gần nhất
  turns: number;      // số lượt hỏi–đáp trong phiên
  title: string;      // câu hỏi đầu tiên (đã rút gọn ở backend)
};

/** Một lượt hỏi–đáp trong phiên. */
export type HistoryTurn = {
  id: number;
  created_at: string;
  question: string;
  answer: string;
  tools: string[];          // công cụ Trợ lý đã gọi để lấy số liệu
  sources: string[];        // nguồn dữ liệu trích dẫn kèm câu trả lời
  packs: string[] | null;   // gói kỹ năng bật lúc hỏi (null = dùng tất cả gói khả dụng)
  advice: string | null;    // mức tư vấn giá sàn — rỗng nếu câu hỏi không phải xin tư vấn
  model: string;
  latency_ms: number;
};

/** Dung lượng log đang lưu — dòng thông tin ở khu dọn log. */
export type HistoryStats = { turns: number; sessions: number; oldest: string | null };

export type HistoryFilters = {
  limit?: number;
  offset?: number;
  username?: string;   // CHỈ admin — tài khoản khác gửi lên cũng bị backend bỏ qua
  date_from?: string;  // YYYY-MM-DD
  date_to?: string;    // YYYY-MM-DD
  q?: string;          // tìm trong câu hỏi
};

/** Bỏ tham số rỗng cho URL sạch — backend hiểu "không có tham số" = không lọc. */
function queryString(filters: HistoryFilters): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") qs.set(key, String(value));
  }
  return qs.toString();
}

/** Danh sách phiên — PHÂN TRANG Ở SERVER (`limit`/`offset`); `total` để vẽ thanh phân trang.
 *  Cố ý không có hàm "tải hết rồi lọc ở client": log hỏi đáp chỉ phình thêm theo thời gian. */
export async function fetchSessions(
  filters: HistoryFilters,
): Promise<{ items: HistorySession[]; total: number }> {
  const qs = queryString(filters);
  return apiFetch<{ items: HistorySession[]; total: number }>(qs ? `${BASE}?${qs}` : BASE);
}

/** Toàn bộ lượt hỏi–đáp của một phiên. */
export async function fetchSessionTurns(sessionId: string): Promise<HistoryTurn[]> {
  const res = await apiFetch<{ items: HistoryTurn[] }>(`${BASE}/${encodeURIComponent(sessionId)}`);
  return res.items;
}

/** Xoá một phiên (chỉ admin) → số lượt đã xoá. */
export async function deleteSession(sessionId: string): Promise<number> {
  const res = await apiFetch<{ deleted: number }>(
    `${BASE}/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
  return res.deleted;
}

/** Dọn log cũ: xoá mọi lượt TRƯỚC ngày `before` (YYYY-MM-DD, chỉ admin) → số lượt đã xoá. */
export async function purgeHistoryBefore(before: string): Promise<number> {
  const res = await apiFetch<{ deleted: number }>(
    `${BASE}?before=${encodeURIComponent(before)}`, { method: "DELETE" });
  return res.deleted;
}

/** Thống kê log đang lưu (số lượt · số phiên · mốc cũ nhất) — CHỈ admin gọi được. */
export async function fetchHistoryStats(): Promise<HistoryStats> {
  return apiFetch<HistoryStats>(`${BASE}/stats`);
}
