/* Nguồn tiêu thụ: exploit (khai thác) · purchase (thu mua) · goods (hàng hóa cao su).
   Nhãn ưu tiên `meta.sources` của hợp đồng (server là nguồn sự thật); trang nào không tải meta thì
   dùng bộ nhãn dự phòng dưới đây — cùng chữ với server. */

export const SOURCE_KEYS = ["exploit", "purchase", "goods"] as const;
export type SourceKey = (typeof SOURCE_KEYS)[number];

export const SOURCE_LABELS: Record<SourceKey, string> = {
  exploit: "Khai thác",
  purchase: "Thu mua",
  goods: "Hàng hóa cao su",
};

/** Nhãn một nguồn: lấy theo `meta.sources` nếu có, không thì nhãn dự phòng. */
export const sourceLabel = (key: SourceKey, metaSources?: Record<string, string>): string =>
  metaSources?.[key] ?? SOURCE_LABELS[key];
