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

export const sendChat = (messages: ChatMessage[]) =>
  apiFetch<ChatReply>("/api/assistant/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });
