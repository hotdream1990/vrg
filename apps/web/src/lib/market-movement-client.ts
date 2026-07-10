/* Client API Bản tin biến động — sinh nhận định AI theo nhóm số liệu (bấm-tạo, không lưu). */

import { apiFetch } from "./http";

export type GroupInput = { key: string; label: string; summary: string };
export type GroupAssessment = { key: string; label: string; assessment: string };
export type AssessmentResult = {
  groups: GroupAssessment[];
  overall: string;
  generated_at: string;
};

/** Gửi tóm tắt số liệu các nhóm → AI viết nhận định từng nhóm + tổng thể. */
export const generateAssessment = (groups: GroupInput[]) =>
  apiFetch<AssessmentResult>("/api/market-movement/assessment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ groups }),
  });
