/* Card "Nguồn tham khảo" (theo Logic viết bản tin tuần mục I. SOURCE): nhóm theo loại, mỗi nguồn
   có vai trò, cách lấy (mode), link, mục dùng và hướng dẫn thu gọn. Chỉ hiện nguồn đang bật. */

import { LinkOutlined } from "@ant-design/icons";

import {
  type WeeklySource,
  type WeeklySourceMeta,
  optionLabel,
} from "../../../../lib/weekly-sources-client";
import { safeHref } from "./WeeklyFormat";

type Props = { sources: WeeklySource[]; meta: WeeklySourceMeta; error?: string };

export default function WeeklySourcesCard({ sources, meta, error }: Props) {
  const enabled = sources.filter((s) => s.enabled).sort((a, b) => a.sort_order - b.sort_order);
  const disabledCount = sources.length - enabled.length;
  const catKeys = [
    ...meta.categories.map((c) => c.key),
    ...new Set(enabled.map((s) => s.category).filter((c) => !meta.categories.some((m) => m.key === c))),
  ];
  const groups = catKeys
    .map((key) => ({ key, items: enabled.filter((s) => s.category === key) }))
    .filter((g) => g.items.length);

  if (error) return <div className="blt-error">{error}</div>;
  if (!enabled.length) return <div className="scan-empty">Chưa có nguồn tham khảo nào đang bật.</div>;

  return (
    <div className="wk-src">
      {groups.map((g) => (
        <div key={g.key} className="wk-src-group">
          <div className="wk-subtle-title">{optionLabel(meta.categories, g.key)}</div>
          {g.items.map((s) => (
            <div key={s.id} className="wk-src-item">
              <div className="wk-src-line">
                {safeHref(s.url) ? (
                  <a className="wk-strong" href={safeHref(s.url) ?? undefined} target="_blank" rel="noopener noreferrer">
                    {s.name} <LinkOutlined />
                  </a>
                ) : <span className="wk-strong">{s.name}</span>}
                <span className="chip info">{optionLabel(meta.modes, s.mode)}</span>
                {(s.sections ?? []).length > 0 && (
                  <span className="wk-muted">Dùng cho mục: {s.sections.join(", ")}</span>
                )}
              </div>
              {s.role && <div className="wk-src-role">{s.role}</div>}
              {s.guide && (
                <details className="wk-src-guide">
                  <summary>Hướng dẫn lấy số liệu</summary>
                  <div className="wk-pre">{s.guide}</div>
                </details>
              )}
            </div>
          ))}
        </div>
      ))}
      {disabledCount > 0 && <div className="wk-muted">{disabledCount} nguồn đang tắt (xem trong Quản lý nguồn).</div>}
    </div>
  );
}
