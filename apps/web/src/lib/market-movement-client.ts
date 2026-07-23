/* Client API Bản tin biến động — sinh nhận định AI theo nhóm số liệu (bấm-tạo, không lưu). */

import { apiFetch } from "./http";

export type GroupInput = { key: string; label: string; summary: string };
/** GroupInput + siêu dữ liệu để minh bạch nguồn/phạm vi trên UI (không gửi lên AI). */
export type GroupMeta = GroupInput & {
  source: string;          // mô tả nguồn dữ liệu đang nạp
  range: string;           // khoảng ngày dữ liệu (đã định dạng)
  latest: string | null;   // ngày mới nhất (ISO) để tính độ tươi
  ok: boolean;             // có số liệu thật hay "Chưa đủ dữ liệu"
};
export type GroupAssessment = { key: string; label: string; assessment: string };
/** Gợi ý xu hướng ngắn hạn (tham khảo) — AI suy từ chính các nhóm số liệu trên. */
export type TrendSuggestion = {
  direction: string;   // Tăng | Tăng nhẹ | Đi ngang | Giảm nhẹ | Giảm
  outlook: string;     // 2–3 câu giải thích + hàm ý điều hành giá sàn
  watch: string[];     // điểm cần theo dõi
};
export type AssessmentResult = {
  groups: GroupAssessment[];
  overall: string;
  trend?: TrendSuggestion | null;
  generated_at: string;
};

/** Gửi tóm tắt số liệu các nhóm → AI viết nhận định từng nhóm + tổng thể.
 *  Chỉ gửi {key,label,summary} — bỏ siêu dữ liệu minh bạch (source/range/…) chỉ dùng ở UI. */
export const generateAssessment = (groups: GroupInput[]) =>
  apiFetch<AssessmentResult>("/api/market-movement/assessment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      groups: groups.map((g) => ({ key: g.key, label: g.label, summary: g.summary })),
    }),
  });
