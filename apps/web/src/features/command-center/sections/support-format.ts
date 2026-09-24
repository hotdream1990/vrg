/* Nhãn + định dạng dùng chung cho các màn Hỗ trợ & Thông báo. */

import type { ThreadKind } from "../../../lib/support-client";

export const KIND_LABEL: Record<ThreadKind, string> = {
  request: "Yêu cầu hỗ trợ",
  announce: "Thông báo",
  reminder: "Nhắc lịch",
  alert: "Cảnh báo tự động",
};

/** Màu thẻ loại tin — dùng chung cho hộp thư, đợt gửi và chi tiết luồng. */
export const KIND_COLOR: Record<ThreadKind, string> = {
  request: "gold",
  announce: "blue",
  reminder: "purple",
  alert: "red",
};

export const REPEAT_LABEL: Record<string, string> = {
  once: "Một lần",
  daily: "Hằng ngày",
  weekly: "Hằng tuần",
  monthly: "Hằng tháng",
};

export const SCOPE_LABEL: Record<string, string> = {
  all: "Tất cả đơn vị",
  units: "Chọn đơn vị",
  region: "Theo khu vực",
};

/** Thời điểm ISO → 'HH:mm DD/MM/YYYY' (chuẩn VN). Chuỗi hỏng thì trả nguyên gốc. */
export function stampVN(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())} ${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`;
}
