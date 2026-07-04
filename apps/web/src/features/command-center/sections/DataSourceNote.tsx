import { DownOutlined, EditOutlined, RightOutlined, RobotOutlined } from "@ant-design/icons";
import { useState } from "react";

import { DATA_SOURCE_NOTES, type DataSourceNote as Note, type SourceKind } from "./data-source-notes";

const KIND: Record<SourceKind, { label: string; icon: React.ReactNode; cls: string }> = {
  auto: { label: "Số liệu tự động", icon: <RobotOutlined />, cls: "dsn-auto" },
  manual: { label: "Số liệu thủ công", icon: <EditOutlined />, cls: "dsn-manual" },
};

/** Hộp gập "Cách lấy số liệu" cho mỗi trang — mặc định ẩn, bấm để hiện chi tiết. */
export default function DataSourceNote({ page }: { page: string }) {
  const note: Note | undefined = DATA_SOURCE_NOTES[page];
  const [open, setOpen] = useState(false);
  if (!note) return null;
  const k = KIND[note.kind];

  return (
    <div className={`dsn ${k.cls}`}>
      <button type="button" className="dsn-head" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="dsn-badge">{k.icon} {k.label}</span>
        <span className="dsn-tagline">{note.tagline}</span>
        <span className="dsn-toggle">{open ? "Thu gọn" : "Cách lấy số liệu"} {open ? <DownOutlined /> : <RightOutlined />}</span>
      </button>

      {open && (
        <div className="dsn-body">
          {note.intro && <p className="dsn-intro">{note.intro}</p>}
          {note.sources.map((s, i) => (
            <div className="dsn-source" key={i}>
              <div className="dsn-source-name">
                {s.name}
                {s.method && <span className="dsn-method">{s.method}</span>}
              </div>
              <dl className="dsn-kv">
                <dt>Lấy ở đâu</dt>
                <dd><Where where={s.where} /></dd>
                <dt>Cách vào</dt>
                <dd><ol>{s.steps.map((t, j) => <li key={j}>{t}</li>)}</ol></dd>
                <dt>Trường lấy</dt>
                <dd><code>{s.field}</code></dd>
                {s.unit && (<><dt>Đơn vị</dt><dd>{s.unit}</dd></>)}
                {s.note && (<><dt>Lưu ý</dt><dd>{s.note}</dd></>)}
              </dl>
            </div>
          ))}
          {note.caveats && note.caveats.length > 0 && (
            <ul className="dsn-caveats">{note.caveats.map((c, i) => <li key={i}>{c}</li>)}</ul>
          )}
        </div>
      )}
    </div>
  );
}

/** URL sạch → link mở tab mới; URL có {placeholder} → hiện dạng code; còn lại → text thường. */
function Where({ where }: { where: string }) {
  const isUrl = /^https?:\/\//.test(where);
  if (isUrl && !where.includes("{"))
    return <a className="dsn-link" href={where} target="_blank" rel="noreferrer">{where}</a>;
  if (isUrl) return <code className="dsn-url">{where}</code>;
  return <span>{where}</span>;
}
