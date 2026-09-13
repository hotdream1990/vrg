/* Chip các nguồn tham khảo (đã bật) dùng cho 1 mục báo cáo — bấm mở trang nguồn ở tab mới. */

import { LinkOutlined } from "@ant-design/icons";
import { Tooltip } from "antd";

import { useWeeklyEditor } from "./WeeklyEditorContext";
import { safeHref } from "./WeeklyFormat";

export default function WeeklySourceChips({ code }: { code: string }) {
  const { sources } = useWeeklyEditor();
  if (!code) return null;
  const list = sources.filter((s) => s.enabled && (s.sections ?? []).includes(code));
  if (!list.length) return null;
  return (
    <div className="wk-chips">
      <span className="wk-chips-label">Nguồn tham khảo:</span>
      {list.map((s) => {
        const tip = [s.role, s.guide].filter(Boolean).join(" — ");
        const href = safeHref(s.url);
        const body = href ? (
          <a className="chip info wk-chip" href={href} target="_blank" rel="noopener noreferrer">
            <LinkOutlined /> {s.name}
          </a>
        ) : (
          <span className="chip wk-chip">{s.name}</span>
        );
        return tip
          ? <Tooltip key={s.id} title={<span style={{ whiteSpace: "pre-line" }}>{tip}</span>}>{body}</Tooltip>
          : <span key={s.id}>{body}</span>;
      })}
    </div>
  );
}
