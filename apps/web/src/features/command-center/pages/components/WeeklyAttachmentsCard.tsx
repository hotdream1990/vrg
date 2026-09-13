/* Tài liệu đính kèm hỗ trợ viết báo cáo tuần (vd báo cáo ANRPC): tải lên PDF/DOCX, danh sách,
   xem chữ trích được. Mỗi tuần (week_key) một bộ tài liệu riêng. */

import { UploadOutlined } from "@ant-design/icons";
import { Modal, Select } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ATTACHMENT_ACCEPT,
  type AttachmentKind,
  type WeeklyAttachment,
  attachmentText,
  deleteAttachment,
  listAttachments,
  uploadAttachment,
} from "../../../../lib/weekly-report-inputs-client";
import WeeklyAttachmentItem, { KIND_OPTIONS } from "./WeeklyAttachmentItem";

type Props = { weekKey: string; canEdit: boolean };
type TextView = { name: string; text: string | null; err?: string } | null;

export default function WeeklyAttachmentsCard({ weekKey, canEdit }: Props) {
  const [items, setItems] = useState<WeeklyAttachment[]>([]);
  const [kind, setKind] = useState<AttachmentKind>("anrpc");
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState("");
  const [view, setView] = useState<TextView>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Bỏ kết quả về muộn của tuần cũ (đổi tuần nhanh) — tránh hiện nhầm tài liệu tuần khác.
  const current = useRef(weekKey);
  const load = useCallback(() => {
    const wk = weekKey;
    listAttachments(wk)
      .then((xs) => { if (current.current === wk) setItems(xs); })
      .catch((e) => { if (current.current === wk) setErr(e instanceof Error ? e.message : "Lỗi"); });
  }, [weekKey]);
  useEffect(() => { current.current = weekKey; setItems([]); setErr(""); load(); }, [weekKey, load]);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true); setErr("");
    try { await uploadAttachment(weekKey, file, kind); load(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Tải file lên thất bại"); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const remove = async (a: WeeklyAttachment) => {
    if (!confirm(`Xoá tài liệu "${a.filename}"?`)) return;
    setErr("");
    try { await deleteAttachment(weekKey, a.id); setItems((xs) => xs.filter((x) => x.id !== a.id)); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi xoá"); }
  };

  const viewText = async (a: WeeklyAttachment) => {
    setView({ name: a.filename, text: null });
    try { const r = await attachmentText(weekKey, a.id); setView({ name: a.filename, text: r.text }); }
    catch (e) { setView({ name: a.filename, text: "", err: e instanceof Error ? e.message : "Lỗi" }); }
  };

  return (
    <div className="wk-atts">
      {canEdit && (
        <>
          <div className="form-note wk-hint">
            Tải báo cáo ANRPC (PDF) hoặc tài liệu tham khảo. AI chỉ dùng số liệu cung–cầu từ các tài liệu này.
          </div>
          <div className="wk-att-upload">
            <Select size="small" style={{ width: 110 }} value={kind} options={KIND_OPTIONS} onChange={setKind} />
            <input ref={fileRef} type="file" accept={ATTACHMENT_ACCEPT} hidden
              onChange={(e) => upload(e.target.files?.[0])} />
            <button className="btn" disabled={uploading} onClick={() => fileRef.current?.click()}>
              {uploading ? <><span className="spinner" /> Đang tải lên và trích chữ…</> : <><UploadOutlined /> Tải tài liệu (PDF/DOCX)</>}
            </button>
          </div>
        </>
      )}
      {err && <div className="blt-error">{err}</div>}
      {items.length === 0 ? (
        <div className="scan-empty">Chưa có tài liệu đính kèm cho kỳ này.</div>
      ) : items.map((a) => (
        <WeeklyAttachmentItem key={a.id} weekKey={weekKey} att={a} canEdit={canEdit}
          onUpdated={(u) => setItems((xs) => xs.map((x) => (x.id === u.id ? { ...x, ...u } : x)))}
          onDelete={remove} onViewText={viewText} />
      ))}

      {view && (
        <Modal open width="min(900px, 94vw)" title={`Nội dung trích được — ${view.name}`} footer={null}
          onCancel={() => setView(null)} destroyOnHidden>
          {view.err ? <div className="blt-error">{view.err}</div>
            : view.text === null ? <div className="blt-loading"><span className="spinner" /> Đang tải…</div>
              : <pre className="wk-pre wk-text-view">{view.text || "(Không có chữ)"}</pre>}
        </Modal>
      )}
    </div>
  );
}
