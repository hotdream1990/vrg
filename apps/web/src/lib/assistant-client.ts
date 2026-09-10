/* Client Trợ lý AI — hỏi đáp số liệu nội bộ + tư vấn giá sàn (tool-calling).
   Gác bằng cap `assistant` (admin + chuyên viên được cấp). */

import { apiFetch } from "./http";

export type TableArtifact = {
  type: "table";
  title: string;
  columns: { key: string; label: string }[];
  rows: Record<string, unknown>[];
};
export type LineArtifact = {
  type: "line";
  title: string;
  labels: string[];
  series: { name: string; values: (number | null)[] }[];
  y_label?: string;
};
export type ChatArtifact = TableArtifact | LineArtifact;

export type ChatMessage = { role: "user" | "assistant"; content: string };
export type ChatReply = { answer: string; artifacts: ChatArtifact[]; sources: string[] };

/** Gói kỹ năng — nhóm công cụ Trợ lý được phép tra cứu.
 *  `core`   = gói nền, luôn bật, người dùng không tắt được.
 *  `active` = tài khoản có quyền dùng VÀ admin chưa tắt trong Cấu hình hệ thống. */
export type SkillPack = {
  key: string;
  label: string;
  desc: string;
  core: boolean;
  active: boolean;
  tools: number;
};

/** Mức tư vấn — Trợ lý được phép khuyên tới đâu.
 *  `data`     = chỉ trả số liệu, không khuyến nghị nâng/giữ/hạ.
 *  `model`    = nêu đúng đề xuất của mô hình, không tự điều chỉnh.
 *  `adjusted` = được lệch khỏi mức mô hình theo bối cảnh, phải giải trình. */
export type AdviceLevel = "data" | "model" | "adjusted";

export const fetchPacks = () => apiFetch<{ packs: SkillPack[] }>("/api/assistant/packs");

/** Gửi câu hỏi kèm phạm vi tra cứu (`packs`) + mức tư vấn (`advice`) + mã phiên (`sessionId`).
 *  Bỏ trống `packs` = backend dùng TẤT CẢ gói khả dụng — nên khi rỗng ta không gửi trường này,
 *  tránh gửi mảng rỗng rồi bị hiểu nhầm thành "không cho tra cứu gì cả". Tương tự với `advice`:
 *  không gửi = backend giữ mức mặc định của nó. */
export const sendChat = (messages: ChatMessage[], packs?: string[], advice?: AdviceLevel,
                         sessionId?: string) =>
  apiFetch<ChatReply>("/api/assistant/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages,
      ...(packs && packs.length > 0 ? { packs } : {}),
      ...(advice ? { advice } : {}),
      // Thiếu session_id là máy chủ KHÔNG ghi nhật ký hỏi–đáp (trang "Lịch sử hỏi đáp" sẽ trống).
      ...(sessionId ? { session_id: sessionId } : {}),
    }),
  });
