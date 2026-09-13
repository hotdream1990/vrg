/* Card "Báo cáo đã lưu" — nhãn kỳ do máy chủ trả (list_label). Khoá đổi tuần khi AI đang chạy. */

import type { WeeklyReportSummary } from "../../../../lib/weekly-report-client";

type Props = {
  list: WeeklyReportSummary[];
  activeKey: string | null;
  canEdit: boolean;
  disabled: boolean;
  onOpen: (weekKey: string) => void;
};

export default function WeeklySavedList({ list, activeKey, canEdit, disabled, onOpen }: Props) {
  return (
    <div className="card wk-card">
      <div className="card-head"><h3>Báo cáo đã lưu</h3></div>
      {list.length === 0 ? (
        <div className="scan-empty">
          {canEdit ? "Chưa có báo cáo — chọn ngày rồi bấm \"Mở / Tạo tuần\"." : "Chưa có báo cáo nào."}
        </div>
      ) : (
        <div className="wk-saved-list">
          {list.map((s) => (
            <button key={s.week_key} className={`btn${activeKey === s.week_key ? " btn-primary" : ""}`}
              disabled={disabled} onClick={() => onOpen(s.week_key)}>{s.label}</button>
          ))}
        </div>
      )}
    </div>
  );
}
