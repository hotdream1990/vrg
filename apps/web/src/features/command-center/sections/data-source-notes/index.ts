import { AUTO_NOTES } from "./auto";
import { MANUAL_NOTES } from "./manual";
import type { DataSourceNote } from "./types";

export type { DataSourceNote, SourceDetail, SourceKind } from "./types";

/** Toàn bộ ghi chú "cách lấy số liệu", gộp 2 loại tự động + thủ công, key theo id trang. */
export const DATA_SOURCE_NOTES: Record<string, DataSourceNote> = {
  ...AUTO_NOTES,
  ...MANUAL_NOTES,
};
