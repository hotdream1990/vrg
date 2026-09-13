/* Thân báo cáo tuần theo thứ tự in: Ghi chú đầu báo cáo → I, II → III (bảng + nhận định) → IV → V, VI. */

import { BulbOutlined } from "@ant-design/icons";

import type { MacroSection, WeeklyNarrative, WeeklyReport } from "../../../../lib/weekly-report-client";
import { useWeeklyEditor } from "./WeeklyEditorContext";
import { joinVi, macroSourceCode } from "./WeeklyFormat";
import WeeklyListField, { HINT_BULLETS, HINT_FORECAST } from "./WeeklyListField";
import WeeklyTables from "./WeeklyTables";

type Props = {
  report: WeeklyReport;
  setNar: (patch: Partial<WeeklyNarrative>) => void;
  setMacro: (i: number, patch: Partial<MacroSection>) => void;
};

const MERGE_PREFIX = "Bản tin tuần này được gộp chung";

export default function WeeklyWritingSections({ report: r, setNar, setMacro }: Props) {
  const { readOnly, aiAll, aiBusy } = useWeeklyEditor();
  const n = r.narrative;
  const weeks = r.weeks ?? [];
  const merged = weeks.length > 2;

  // Câu mẫu gộp tuần — người dùng tự điền lý do sau "do …". Thay đúng dòng gợi ý cũ nếu đã có.
  const suggestNote = () => {
    const periods = joinVi(weeks.slice(1).map((w) => `Tuần ${w.week_no} (${w.range})`));
    const line = `${MERGE_PREFIX} phân tích diễn biến giai đoạn ${periods} do …`;
    const rest = (n.report_note ?? []).filter((s) => s.trim() && !s.startsWith(MERGE_PREFIX));
    setNar({ report_note: [line, ...rest] });
  };

  return (
    <>
      <div className="card blt-section blt-editable wk-card">
        <WeeklyListField fieldKey="report_note" label="Ghi chú đầu báo cáo" ai={false} minHeight={48}
          items={n.report_note ?? []} onChange={(v) => setNar({ report_note: v })}
          placeholder={merged ? "Vd: lý do gộp tuần (nghỉ lễ…)" : "Không bắt buộc — in dưới tiêu đề báo cáo"}
          extra={merged && !readOnly ? (
            <button className="btn btn-sm" onClick={suggestNote}><BulbOutlined /> Gợi ý ghi chú gộp tuần</button>
          ) : undefined} />
      </div>

      <div className="card blt-section blt-editable wk-card">
        <WeeklyListField fieldKey="summary_prev" label={`I. Tóm tắt ${r.prev_label || `tuần ${r.prev_week_no}/${r.prev_year}`}`}
          items={n.summary_prev} onChange={(v) => setNar({ summary_prev: v })} />
        <WeeklyListField fieldKey="movement" label={`II. Diễn biến ${r.movement_label || `tuần ${r.week_no}/${r.year}`}`}
          hint={merged ? "Kỳ gộp: nên tách đoạn theo từng tuần (Tuần 35 … / Sang Tuần 36 …)." : undefined}
          items={n.movement} onChange={(v) => setNar({ movement: v })} minHeight={110} />
      </div>

      <div className="card blt-section blt-editable wk-card">
        <div className="blt-section-header"><h3>III. Diễn biến giá</h3></div>
        <WeeklyTables report={r} setNar={setNar} />
      </div>

      <div className="card blt-section blt-editable wk-card">
        <div className="blt-section-header"><h3>IV. Các yếu tố vĩ mô</h3></div>
        {n.macro.map((m, i) => (
          <WeeklyListField key={i} fieldKey={`macro:${i}`} sourceCode={macroSourceCode(m.title, i)}
            hint={HINT_BULLETS} items={m.bullets}
            onChange={(v) => setMacro(i, { bullets: v })}
            label={readOnly ? m.title : (
              <input className="blt-input wk-title-input" value={m.title} aria-label={`Tiêu đề nhóm IV.${i + 1}`}
                readOnly={aiAll || aiBusy === `macro:${i}`}
                onChange={(e) => setMacro(i, { title: e.target.value })} />
            )} />
        ))}
      </div>

      <div className="card blt-section blt-editable wk-card">
        <WeeklyListField fieldKey="forecast" label={`V. Dự báo xu hướng ${r.next_label || `tuần ${r.next_week_no}/${r.next_year}`}`}
          hint={HINT_FORECAST} items={n.forecast} onChange={(v) => setNar({ forecast: v })} />
        <WeeklyListField fieldKey="conclusion" label="VI. Kết luận và khuyến nghị"
          items={n.conclusion} onChange={(v) => setNar({ conclusion: v })} />
      </div>
    </>
  );
}
