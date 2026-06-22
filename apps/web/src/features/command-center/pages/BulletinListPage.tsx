import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  listPublished,
  publishedDownloadUrl,
  type PublishedBulletin,
} from "../../../lib/bulletin-client";
import { useAuth } from "../../auth/AuthContext";
import "../../bulletin/bulletin.css";

/* ── Icons ── */
const IconList = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" /><line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
  </svg>
);
const IconPlus = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);
const IconDownload = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
  </svg>
);
const IconEye = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" />
  </svg>
);
const IconFile = () => (
  <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
  </svg>
);

/* ── Helpers ── */
const fmtSize = (b: number) =>
  b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;

const fmtModified = (iso: string) => {
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? iso
    : d.toLocaleString("vi-VN", {
        day: "2-digit", month: "2-digit", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
};

export default function BulletinListPage() {
  const { canEdit } = useAuth();
  const [items, setItems] = useState<PublishedBulletin[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    listPublished()
      .then((r) => { if (alive) setItems(r.bulletins); })
      .catch((e) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, []);

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><IconList /> Bản tin đã xuất bản</h2>
          <p>Danh sách các bản tin ngày đã xuất (file PPTX)</p>
        </div>
        {canEdit && (
          <div className="actions">
            <Link className="btn btn-primary" to="/ban-tin/tao">
              <IconPlus /> Tạo bản tin mới
            </Link>
          </div>
        )}
      </div>

      {error && <div className="blt-error">{error}</div>}

      {!items && !error && (
        <div className="blt-loading"><span className="spinner" /> Đang tải danh sách...</div>
      )}

      {items && items.length === 0 && (
        <div className="blt-empty">
          <div className="blt-empty-icon"><IconFile /></div>
          <h3>Chưa có bản tin nào</h3>
          <p>{canEdit ? 'Nhấn "Tạo bản tin mới" để tạo và xuất bản tin đầu tiên' : "Chưa có bản tin nào được xuất bản."}</p>
        </div>
      )}

      {items && items.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="blt-list-table">
            <thead>
              <tr>
                <th>Ngày bản tin</th>
                <th>Tên file</th>
                <th className="r">Kích thước</th>
                <th>Xuất lúc</th>
                <th className="r">Tải về</th>
              </tr>
            </thead>
            <tbody>
              {items.map((b) => (
                <tr key={b.filename}>
                  <td style={{ fontWeight: 600 }}>
                    <Link className="blt-link" to={`/ban-tin/xem/${encodeURIComponent(b.filename)}`}>
                      {b.report_date ?? "—"}
                    </Link>
                  </td>
                  <td style={{ color: "var(--muted)" }}>{b.filename}</td>
                  <td className="r">{fmtSize(b.size)}</td>
                  <td style={{ color: "var(--muted)" }}>{fmtModified(b.modified)}</td>
                  <td className="r">
                    <span style={{ display: "inline-flex", gap: 8, justifyContent: "flex-end" }}>
                      <Link className="btn" to={`/ban-tin/xem/${encodeURIComponent(b.filename)}`}>
                        <IconEye /> Xem
                      </Link>
                      <a className="btn" href={publishedDownloadUrl(b.filename)} download>
                        <IconDownload /> Tải
                      </a>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
