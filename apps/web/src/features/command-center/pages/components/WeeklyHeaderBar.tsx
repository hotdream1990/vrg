/* Thanh đầu báo cáo tuần: tiêu đề kỳ + chọn số tuần gộp + trạng thái lưu + AI toàn bộ · Soát số liệu ·
   Xuất PDF · Xoá. */

import {
  CheckCircleOutlined, DeleteOutlined, FilePdfOutlined, RobotOutlined, SafetyCertificateOutlined,
} from "@ant-design/icons";
import { Segmented, Tooltip } from "antd";

import type { WeeklyReport } from "../../../../lib/weekly-report-client";
import type { SaveState } from "./useWeeklyDraft";

type Props = {
  report: WeeklyReport;
  canEdit: boolean;
  save: SaveState;
  savedAt: string;
  aiAll: boolean;
  /** AI của 1 ô đang chạy → khoá "AI hỗ trợ toàn bộ" (và ngược lại). */
  aiOne: boolean;
  busy: boolean;
  /** Đang soát chữ nhận định với dữ liệu hiện tại. */
  checking: boolean;
  onSpan: (n: number) => void;
  onAiAll: () => void;
  onCheck: () => void;
  onPdf: () => void;
  onDelete: () => void;
};

const SPAN_OPTIONS = [1, 2, 3].map((n) => ({ value: n, label: `${n} tuần` }));

export default function WeeklyHeaderBar({
  report: r, canEdit, save, savedAt, aiAll, aiOne, busy, checking, onSpan, onAiAll, onCheck, onPdf, onDelete,
}: Props) {
  const span = r.narrative.span_weeks ?? r.span_weeks ?? 1;
  // Đã đổi, chờ máy chủ dựng lại bảng — lưu lỗi thì thôi báo "đang dựng" (lỗi hiện ở banner đỏ).
  const pending = span !== (r.span_weeks ?? 1) && save !== "error";
  const saveText = save === "saving" ? "Đang lưu…" : save === "saved" ? `Đã lưu ${savedAt}`
    : save === "error" ? "Lỗi lưu" : "Tự lưu khi nhập";

  return (
    <div className="card blt-section wk-card">
      <div className="blt-section-header" style={{ marginBottom: 0 }}>
        <div className="wk-head-title">
          <h3>{r.title_label || `Tuần ${r.week_no}/${r.year}`} ({r.date_range})</h3>
          <div className="wk-span">
            <span className="wk-muted">Số tuần gộp:</span>
            {canEdit ? (
              <Tooltip title="Gộp các tuần liền nhau (vd tuần có nghỉ lễ). Bảng số, nhãn các phần và PDF đổi theo.">
                <Segmented size="small" value={span} options={SPAN_OPTIONS} disabled={aiAll || aiOne || busy}
                  onChange={(v) => onSpan(Number(v))} />
              </Tooltip>
            ) : <span className="wk-strong">{span} tuần</span>}
            {pending && <span className="wk-muted"><span className="spinner" /> Đang dựng lại bảng…</span>}
          </div>
        </div>
        <div className="blt-section-meta" style={{ alignItems: "center", flexWrap: "wrap" }}>
          {canEdit && (
            <span className={`db-badge${save === "error" ? " err" : ""}`}
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              {save === "saving" ? <span className="spinner" /> : <CheckCircleOutlined />} {saveText}
            </span>
          )}
          {canEdit && (
            <button className="btn btn-primary" onClick={onAiAll} disabled={aiAll || aiOne || busy}>
              {aiAll ? <><span className="spinner" /> Đang tạo…</> : <><RobotOutlined /> AI hỗ trợ toàn bộ</>}
            </button>
          )}
          <Tooltip title="So chữ nhận định đã lưu với bảng số hiện tại (dữ liệu về muộn sau khi AI viết).">
            <button className="btn" onClick={onCheck} disabled={checking || busy || aiAll}>
              {checking ? <span className="spinner" /> : <SafetyCertificateOutlined />} Soát số liệu
            </button>
          </Tooltip>
          <button className="btn" onClick={onPdf} disabled={busy || aiAll || checking}>
            {busy ? <><span className="spinner" /> Đang xử lý…</> : <><FilePdfOutlined /> Xuất PDF</>}
          </button>
          {canEdit && (
            <button className="btn" onClick={onDelete} disabled={busy || aiAll}><DeleteOutlined /> Xoá</button>
          )}
        </div>
      </div>
    </div>
  );
}
