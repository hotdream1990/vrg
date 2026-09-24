/* Client Trợ lý AI — hỏi đáp số liệu nội bộ + tư vấn giá sàn (tool-calling).
   Gác bằng cap `assistant` (admin + chuyên viên được cấp). */

import type { Proposal } from "./floor-proposal-client";
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
/** `proposal` khác null ⇒ Trợ lý vừa lập/chỉnh phương án giá sàn nháp → FE thay phương án của phiên. */
export type ChatReply = {
  answer: string; artifacts: ChatArtifact[]; sources: string[]; proposal?: Proposal | null;
};

/** Một công cụ trong gói. `name` là tên hàm kỹ thuật (chỉ dùng làm khoá, KHÔNG hiện cho người
 *  dùng nghiệp vụ); `desc` là mô tả tiếng Việt "công cụ này tra ra cái gì". */
export type SkillTool = { name: string; label: string; desc: string };

/** Gói kỹ năng — nhóm công cụ Trợ lý được phép tra cứu.
 *  `core`   = gói nền, luôn bật, người dùng không tắt được.
 *  `active` = tài khoản có quyền dùng VÀ admin chưa tắt trong Cấu hình hệ thống.
 *  `cap`    = mã quyền tối thiểu để dùng gói (null = ai vào được Trợ lý cũng dùng được).
 *  `items`  = danh sách công cụ, trả về cả với gói đang tắt/không đủ quyền — để người dùng biết
 *             hệ thống CÓ khả năng đó, chỉ là chưa dùng được. */
export type SkillPack = {
  key: string;
  label: string;
  desc: string;
  core: boolean;
  active: boolean;
  cap: string | null;
  tools: number;
  items: SkillTool[];
};

/** `limits` = những việc Trợ lý CHƯA làm được, hiện thẳng lên giao diện để người dùng không kỳ
 *  vọng nhầm rồi tưởng hệ thống trả lời sai. */
export type PacksReply = { packs: SkillPack[]; limits: string[] };

/** Mức tư vấn — Trợ lý được phép khuyên tới đâu.
 *  `data`     = chỉ trả số liệu, không khuyến nghị nâng/giữ/hạ.
 *  `model`    = nêu đúng đề xuất của mô hình, không tự điều chỉnh.
 *  `adjusted` = được lệch khỏi mức mô hình theo bối cảnh, phải giải trình. */
export type AdviceLevel = "data" | "model" | "adjusted";

export const fetchPacks = () => apiFetch<PacksReply>("/api/assistant/packs");

/** Gửi câu hỏi kèm phạm vi tra cứu (`packs`) + mức tư vấn (`advice`) + mã phiên (`sessionId`).
 *  Bỏ trống `packs` = backend dùng TẤT CẢ gói khả dụng — nên khi rỗng ta không gửi trường này,
 *  tránh gửi mảng rỗng rồi bị hiểu nhầm thành "không cho tra cứu gì cả". Tương tự với `advice`:
 *  không gửi = backend giữ mức mặc định của nó. `proposal` = phương án giá sàn nháp hiện tại của phiên
 *  (để Trợ lý chỉnh tiếp "tăng lên tí xíu"); không có thì không gửi. */
export const sendChat = (messages: ChatMessage[], packs?: string[], advice?: AdviceLevel,
                         sessionId?: string, proposal?: Proposal | null) =>
  apiFetch<ChatReply>("/api/assistant/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages,
      ...(packs && packs.length > 0 ? { packs } : {}),
      ...(advice ? { advice } : {}),
      // Thiếu session_id là máy chủ KHÔNG ghi nhật ký hỏi–đáp (trang "Lịch sử hỏi đáp" sẽ trống).
      ...(sessionId ? { session_id: sessionId } : {}),
      ...(proposal ? { proposal } : {}),
    }),
  });
