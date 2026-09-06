import { DeleteOutlined, FileOutlined, PaperClipOutlined } from "@ant-design/icons";
import { Image, Upload, message } from "antd";
import { useEffect, useState } from "react";

import {
  type Attachment, SUPPORT_ACCEPT, SUPPORT_MAX_MB, downloadSupportFile, fetchAttachmentUrl,
  isImage, uploadSupportFile,
} from "../../../lib/support-client";

/** Ảnh đính kèm — tải qua fetch (kèm Bearer) rồi hiện bằng blob URL.
 *  `<img src>` trần không gửi được token nên endpoint file (có gác quyền theo đơn vị) sẽ trả 401. */
function AttachmentImage({ att }: { att: Attachment }) {
  const [url, setUrl] = useState<string>("");
  useEffect(() => {
    let revoked = "";
    fetchAttachmentUrl(att).then((u) => { revoked = u; setUrl(u); }).catch(() => setUrl(""));
    return () => { if (revoked) URL.revokeObjectURL(revoked); };
  }, [att]);
  if (!url) return <span className="sp-file"><FileOutlined /> {att.filename}</span>;
  return <Image src={url} alt={att.filename} height={96} style={{ borderRadius: 8, objectFit: "cover" }} />;
}

/** Danh sách đính kèm của một tin: ảnh xem ngay, tài liệu bấm để tải về. */
export function AttachmentList({ files }: { files: Attachment[] }) {
  if (!files?.length) return null;
  return (
    <div className="sp-attachments">
      {files.map((att) => (isImage(att)
        ? <AttachmentImage key={att.file} att={att} />
        : (
          <button key={att.file} type="button" className="sp-file"
            onClick={() => downloadSupportFile(att).catch((e) => message.error(e.message))}>
            <PaperClipOutlined /> {att.filename}
          </button>
        )
      ))}
    </div>
  );
}

/** Ô chọn file khi soạn tin: upload ngay lúc chọn, trả về danh sách đã lưu để gắn vào tin. */
export function AttachmentPicker({ value, onChange, disabled }: {
  value: Attachment[];
  onChange: (files: Attachment[]) => void;
  disabled?: boolean;
}) {
  const [busy, setBusy] = useState(false);

  const add = async (file: File) => {
    if (file.size > SUPPORT_MAX_MB * 1024 * 1024) {
      message.error(`File quá lớn (tối đa ${SUPPORT_MAX_MB} MB).`);
      return;
    }
    setBusy(true);
    try {
      onChange([...value, await uploadSupportFile(file)]);
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <Upload accept={SUPPORT_ACCEPT} showUploadList={false} disabled={disabled || busy}
        beforeUpload={(file) => { void add(file as unknown as File); return false; }}>
        <button type="button" className="btn" disabled={disabled || busy}>
          <PaperClipOutlined /> {busy ? "Đang tải lên…" : "Đính kèm file / hình ảnh"}
        </button>
      </Upload>
      {value.length > 0 && (
        <div className="sp-attachments" style={{ marginTop: 8 }}>
          {value.map((att) => (
            <span key={att.file} className="sp-file">
              <PaperClipOutlined /> {att.filename}
              <DeleteOutlined style={{ marginLeft: 8, cursor: "pointer" }}
                onClick={() => onChange(value.filter((f) => f.file !== att.file))} />
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
