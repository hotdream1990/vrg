/* 1 tài liệu đính kèm của báo cáo tuần: thông tin file · đổi loại · tải về · xem chữ trích được ·
   AI tóm tắt số liệu chính · tóm tắt sửa tay (lưu khi rời ô) · xoá. */

import {
  DeleteOutlined, DownloadOutlined, FileSearchOutlined, FileTextOutlined, RobotOutlined, StopOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Select } from "antd";
import { useEffect, useState } from "react";

import {
  type AttachmentKind,
  type WeeklyAttachment,
  downloadAttachment,
  patchAttachment,
  summarizeAttachment,
} from "../../../../lib/weekly-report-inputs-client";
import { viDate } from "./WeeklyFormat";

type Props = {
  weekKey: string;
  att: WeeklyAttachment;
  canEdit: boolean;
  onUpdated: (a: WeeklyAttachment) => void;
  onDelete: (a: WeeklyAttachment) => void;
  onViewText: (a: WeeklyAttachment) => void;
};

export const KIND_OPTIONS: { value: AttachmentKind; label: string }[] = [
  { value: "anrpc", label: "ANRPC" },
  { value: "other", label: "Khác" },
];

const size = (b: number) => (b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

export default function WeeklyAttachmentItem({ weekKey, att, canEdit, onUpdated, onDelete, onViewText }: Props) {
  const [summary, setSummary] = useState(att.summary ?? "");
  const [busy, setBusy] = useState<"" | "kind" | "summary" | "ai" | "download">("");
  const [err, setErr] = useState("");
  const [warns, setWarns] = useState<string[]>([]);
  useEffect(() => { setSummary(att.summary ?? ""); }, [att.summary]);

  const run = async (tag: typeof busy, fn: () => Promise<void>) => {
    setBusy(tag); setErr("");
    try { await fn(); } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); } finally { setBusy(""); }
  };

  const setKind = (kind: AttachmentKind) =>
    run("kind", async () => onUpdated(await patchAttachment(weekKey, att.id, { kind })));
  const saveSummary = () => {
    if (summary === (att.summary ?? "")) return;
    run("summary", async () => onUpdated(await patchAttachment(weekKey, att.id, { summary })));
  };
  const aiSummary = () => {
    if (summary.trim() && !confirm("Thay phần tóm tắt đang có bằng bản AI tóm tắt?")) return;
    run("ai", async () => {
      const r = await summarizeAttachment(weekKey, att.id);
      setSummary(r.summary);
      setWarns(r.warnings ?? []);
      onUpdated({ ...att, summary: r.summary });
    });
  };

  const noText = !att.text_chars;
  return (
    <div className="wk-att">
      <div className="wk-att-head">
        <FileTextOutlined className="wk-att-icon" />
        <div className="wk-att-meta">
          <div className="wk-strong wk-ellipsis" title={att.filename}>{att.filename}</div>
          <div className="wk-muted">
            {size(att.size)}{att.pages ? ` · ${att.pages} trang` : ""} · {(att.text_chars ?? 0).toLocaleString("vi-VN")} ký tự trích được
            {att.uploaded_by ? ` · ${att.uploaded_by}` : ""}{att.created_at ? ` · ${viDate(att.created_at)}` : ""}
          </div>
        </div>
        <Select size="small" style={{ width: 96 }} value={att.kind} options={KIND_OPTIONS}
          disabled={!canEdit || busy === "kind"} onChange={setKind} />
        <button className="btn btn-sm" title="Tải về" disabled={busy === "download"}
          onClick={() => run("download", () => downloadAttachment(weekKey, att))}><DownloadOutlined /></button>
        <button className="btn btn-sm" onClick={() => onViewText(att)} disabled={noText}>
          <FileSearchOutlined /> Xem nội dung
        </button>
        {canEdit && (
          <button className="btn btn-sm" onClick={aiSummary} disabled={noText || !!busy}>
            {busy === "ai" ? <span className="spinner" /> : <RobotOutlined />} AI tóm tắt số liệu chính
          </button>
        )}
        {canEdit && (
          <button className="btn btn-sm" title="Xoá" onClick={() => onDelete(att)} disabled={!!busy}>
            <DeleteOutlined />
          </button>
        )}
      </div>
      {noText && (
        <div className="wk-abs"><StopOutlined /> Không trích được chữ (có thể là ảnh scan) — AI không đọc được</div>
      )}
      <div className="wk-att-summary">
        <div className="wk-subtle-title">
          Tóm tắt số liệu chính {busy === "summary" && <span className="spinner" />}
        </div>
        <textarea className="blt-textarea" rows={4} value={summary} readOnly={!canEdit}
          placeholder={canEdit ? "Bấm \"AI tóm tắt số liệu chính\" hoặc tự ghi các số cung–cầu cần dùng…" : ""}
          onChange={(e) => { setSummary(e.target.value); setWarns([]); }} onBlur={saveSummary} />
        {warns.length > 0 && (
          <div className="wk-ai-warn"><WarningOutlined /> Số không tìm thấy nguyên văn trong tài liệu — kiểm lại: {warns.join("; ")}</div>
        )}
        {canEdit && <div className="form-note wk-hint">AI viết báo cáo ưu tiên đọc phần tóm tắt này (tự lưu khi rời ô).</div>}
      </div>
      {err && <div className="blt-error">{err}</div>}
    </div>
  );
}
