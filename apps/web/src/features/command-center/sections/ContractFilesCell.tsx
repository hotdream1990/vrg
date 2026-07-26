/* Ô đính kèm NHIỀU chứng từ — dùng chung cho biểu Tiêu thụ (bộ HĐ · phiếu xuất kho · hoá đơn)
   và Tồn kho (HĐ đã ký scan).

   Mỗi file là một "chip": bấm tên để mở, bấm × để bỏ khỏi dòng. Chọn được NHIỀU file một lần
   (tải lần lượt rồi gộp vào danh sách một lượt — tránh mỗi file một lần setState làm mất file
   trước đó). Bỏ file khỏi dòng CHỈ gỡ liên kết, không xoá file trên server. */

import { DeleteOutlined, UploadOutlined } from "@ant-design/icons";
import { Tooltip, Upload, message } from "antd";
import { useState } from "react";

import { CONTRACT_ACCEPT, CONTRACT_MAX_MB } from "../../../lib/contract-upload";
import { MAX_DOCS, type ContractDoc } from "../../../lib/contract-docs";
import { type Role, openContractFile, uploadContractFile } from "../../../lib/unit-daily-client";

type Props = {
  docs: ContractDoc[];
  onChange: (docs: ContractDoc[]) => void;
  role: Role;
  readOnly?: boolean;
  addLabel?: string;             // nhãn nút thêm (mặc định "Chọn" / "Thêm" khi đã có file)
};

const NAME_MAX = 16;             // cắt tên hiển thị cho vừa ô, tên đầy đủ xem ở tooltip

export default function ContractFilesCell({ docs, onChange, role, readOnly, addLabel }: Props) {
  const [busy, setBusy] = useState(false);

  /** Tải CẢ LÔ file người dùng vừa chọn rồi gộp một lượt vào danh sách. */
  const uploadBatch = async (files: File[]) => {
    const room = MAX_DOCS - docs.length;
    if (room <= 0) {
      message.warning(`Mỗi mục chỉ đính kèm tối đa ${MAX_DOCS} file.`);
      return;
    }
    const batch = files.slice(0, room);
    if (batch.length < files.length) {
      message.warning(`Chỉ nhận thêm ${room} file (tối đa ${MAX_DOCS} file mỗi mục).`);
    }
    setBusy(true);
    const added: ContractDoc[] = [];
    for (const f of batch) {
      try {
        const r = await uploadContractFile(role, f);
        added.push({ file: r.file, filename: r.filename });
      } catch (e) {
        message.error(`${f.name}: ${(e as Error).message || "tải lên thất bại"}`);
      }
    }
    setBusy(false);
    if (!added.length) return;
    onChange([...docs, ...added]);
    message.success(`Đã tải lên ${added.length} chứng từ.`);
  };

  const remove = (name: string) => onChange(docs.filter((d) => d.file !== name));

  return (
    <span className="ud-files">
      {docs.map((d) => (
        <span key={d.file} className="ud-file-chip">
          <Tooltip title={d.filename}>
            <a onClick={() => openContractFile(role, d.file)}>
              {d.filename.length > NAME_MAX ? `${d.filename.slice(0, NAME_MAX)}…` : d.filename}
            </a>
          </Tooltip>
          {!readOnly && (
            <button type="button" className="ud-file-x" title="Bỏ file khỏi dòng này"
              onClick={() => remove(d.file)}><DeleteOutlined /></button>
          )}
        </span>
      ))}
      {!docs.length && <span style={{ fontSize: 12, color: "var(--muted)" }}>—</span>}
      {!readOnly && (
        <Upload
          showUploadList={false} accept={CONTRACT_ACCEPT} disabled={busy} multiple
          beforeUpload={(file, fileList) => {
            // antd gọi beforeUpload cho TỪNG file; chỉ xử lý ở file đầu để tải cả lô một lần.
            if (file === fileList[0]) void uploadBatch(fileList as File[]);
            return false;
          }}
        >
          <Tooltip title={`Chọn được nhiều file cùng lúc · mỗi file tối đa ${CONTRACT_MAX_MB} MB`}>
            <button type="button" className="btn ud-file-add">
              <UploadOutlined /> {busy ? "…" : (addLabel ?? (docs.length ? "Thêm" : "Chọn"))}
            </button>
          </Tooltip>
        </Upload>
      )}
    </span>
  );
}
