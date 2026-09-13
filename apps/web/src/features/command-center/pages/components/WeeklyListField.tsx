/* Ô viết của Báo cáo tuần: textarea "mỗi dòng một ý" + gợi ý định dạng + chip nguồn tham khảo
   + cảnh báo từ tuyệt đối (đỏ, thời gian thực) + số AI viết chưa đối chiếu được (vàng)
   + chữ đã lưu lệch bảng số hiện tại (vàng, sau khi bấm "Soát số liệu"). */

import { RobotOutlined, StopOutlined, WarningOutlined } from "@ant-design/icons";
import type { ReactNode } from "react";

import { useWeeklyEditor } from "./WeeklyEditorContext";
import { findAbsoluteWords, sectionCodeOf } from "./WeeklyFormat";
import WeeklySourceChips from "./WeeklySourceChips";

/** Gợi ý định dạng dùng chung (PDF + web hiểu giống nhau). */
export const HINT_BULLETS = "Định dạng: dòng mở đầu > là gạch cấp 2, >> là cấp 3; **chữ đậm**, *chữ nghiêng*.";
export const HINT_FORECAST = "Định dạng: \"- Hỗ trợ giá: …\" / \"- Kìm hãm đà tăng: …\". Tham khảo Kịch bản 1 "
  + "Tích lũy · Kịch bản 2 Tiếp tục điều chỉnh. **đậm**, *nghiêng*.";

type Props = {
  /** key narrative hoặc `macro:<i>` — dùng cho AI, cảnh báo và mã mục nguồn tham khảo. */
  fieldKey: string;
  label: ReactNode;
  hint?: string;
  items: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  /** Có nút "AI hỗ trợ" cho ô này. */
  ai?: boolean;
  /** Kiểm từ tuyệt đối (tắt với ô ghi chú bảng). */
  checkWords?: boolean;
  /** Nút phụ cạnh nhãn (vd "Gợi ý ghi chú gộp tuần"). */
  extra?: ReactNode;
  minHeight?: number;
  /** Mã mục nguồn tham khảo; mặc định suy từ fieldKey (Phần IV truyền theo chủ đề tiêu đề). */
  sourceCode?: string;
};

export default function WeeklyListField({
  fieldKey, label, hint, items, onChange, placeholder, ai = true, checkWords = true, extra, minHeight = 84, sourceCode,
}: Props) {
  const ed = useWeeklyEditor();
  const text = items.join("\n");
  const abs = checkWords
    ? Array.from(new Set([...findAbsoluteWords(text), ...(ed.aiAbs[fieldKey] ?? [])]))
    : [];
  const warns = ed.aiWarn[fieldKey] ?? [];
  const checks = ed.checkWarn[fieldKey] ?? [];
  const busy = ed.aiBusy === fieldKey;
  // Khoá gõ khi AI đang viết đúng ô này / toàn bộ — kết quả về sẽ ghi đè chữ gõ trong lúc chờ.
  const locked = ed.readOnly || ed.aiAll || busy;

  return (
    <div className="wk-field">
      <div className="wk-field-head">
        <label>{label}</label>
        <div className="wk-field-actions">
          {extra}
          {ai && !ed.readOnly && (
            <button className="btn btn-sm" onClick={() => ed.runAi(fieldKey)}
              disabled={busy || ed.locked || !!ed.aiBusy}>
              {busy ? <span className="spinner" /> : <RobotOutlined />} AI hỗ trợ
            </button>
          )}
        </div>
      </div>
      <WeeklySourceChips code={sourceCode ?? sectionCodeOf(fieldKey)} />
      {hint && !ed.readOnly && <div className="form-note wk-hint">{hint}</div>}
      <textarea className="blt-date-input wk-textarea" style={{ minHeight }}
        value={text} readOnly={locked}
        placeholder={placeholder ?? "Mỗi dòng một ý…"}
        onChange={(e) => {
          if (warns.length || checks.length || ed.aiAbs[fieldKey]?.length) ed.clearWarn(fieldKey);
          onChange(e.target.value.split("\n"));
        }} />
      {abs.length > 0 && (
        <div className="wk-abs"><StopOutlined /> Nên tránh từ tuyệt đối: {abs.join(", ")}</div>
      )}
      {warns.length > 0 && (
        <div className="wk-ai-warn">
          <WarningOutlined /> Số chưa đối chiếu được với dữ liệu: {warns.join("; ")}
        </div>
      )}
      {checks.length > 0 && (
        <div className="wk-ai-warn wk-check-warn">
          <WarningOutlined />
          <div>
            Lệch dữ liệu hiện tại:
            <ul className="wk-check-list">{checks.map((c) => <li key={c}>{c}</li>)}</ul>
          </div>
        </div>
      )}
    </div>
  );
}
