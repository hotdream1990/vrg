/* Ngữ cảnh dùng chung cho các ô viết của Báo cáo tuần: quyền sửa, nguồn tham khảo, trạng thái AI
   và cảnh báo AI theo từng ô — tránh truyền hàng chục prop xuyên qua I…VI. */

import { createContext, useContext } from "react";

import type { WeeklySource } from "../../../../lib/weekly-sources-client";

export type WeeklyEditor = {
  readOnly: boolean;
  sources: WeeklySource[];
  /** key ô đang chạy AI riêng ("" = không). */
  aiBusy: string;
  /** Đang chạy AI toàn bộ → mọi ô viết chỉ đọc (kết quả về sẽ ghi đè chữ gõ trong lúc chờ). */
  aiAll: boolean;
  /** Đang chạy AI toàn bộ / xuất PDF → khoá nút AI từng ô. */
  locked: boolean;
  /** Số AI viết mà không đối chiếu được với dữ liệu — theo key ô (field narrative | `macro:<i>`). */
  aiWarn: Record<string, string[]>;
  aiAbs: Record<string, string[]>;
  /** Kết quả "Soát số liệu": chữ đã lưu lệch bảng số hiện tại — theo key ô (tách nhãn với cảnh báo AI). */
  checkWarn: Record<string, string[]>;
  runAi: (fieldKey: string) => void;
  /** Người dùng sửa ô → xoá cảnh báo AI + cảnh báo soát số liệu của ô đó. */
  clearWarn: (fieldKey: string) => void;
};

const noop = () => undefined;

export const WeeklyEditorContext = createContext<WeeklyEditor>({
  readOnly: true, sources: [], aiBusy: "", aiAll: false, locked: false, aiWarn: {}, aiAbs: {}, checkWarn: {}, runAi: noop, clearWarn: noop,
});

export const useWeeklyEditor = () => useContext(WeeklyEditorContext);
