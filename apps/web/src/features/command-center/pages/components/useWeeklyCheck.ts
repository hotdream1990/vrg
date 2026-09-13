/* Soát "chữ nhận định lệch dữ liệu hiện tại" của Báo cáo tuần (GET /check — không ghi gì).
   Kết quả chỉ áp cho ĐÚNG tuần đã gửi; người dùng sửa ô nào thì bỏ cảnh báo của ô đó. */

import { useCallback, useState } from "react";

import { type WeeklyCheckResult, checkWeeklyReport } from "../../../../lib/weekly-report-client";

export function useWeeklyCheck() {
  const [result, setResult] = useState<WeeklyCheckResult | null>(null);
  const [checking, setChecking] = useState(false);

  /** `isCurrent()`: tuần đang mở còn đúng là `weekKey` không (người dùng có thể đã mở tuần khác). */
  const run = useCallback(async (weekKey: string, isCurrent: () => boolean) => {
    setChecking(true);
    try {
      const r = await checkWeeklyReport(weekKey);
      if (isCurrent()) setResult(r);
      return r;
    } finally {
      setChecking(false);
    }
  }, []);

  /** Soát trước khi xuất PDF: có chỗ lệch → hỏi lại. Soát lỗi → vẫn cho xuất (chỉ là cảnh báo). */
  const confirmExport = useCallback(async (weekKey: string, isCurrent: () => boolean) => {
    const r = await run(weekKey, isCurrent).catch(() => null);
    return !r || r.count === 0 || confirm(`Có ${r.count} chỗ nhận định lệch dữ liệu hiện tại — vẫn xuất PDF?`);
  }, [run]);

  const clearKey = useCallback((key: string) => setResult((r) => {
    if (!r?.warnings[key]) return r;
    const { [key]: _removed, ...rest } = r.warnings;
    return { ...r, warnings: rest };
  }), []);

  const reset = useCallback(() => setResult(null), []);

  return { result, checking, run, confirmExport, clearKey, reset };
}
