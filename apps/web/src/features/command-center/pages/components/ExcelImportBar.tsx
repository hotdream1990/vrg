/* Thanh nhập liệu bằng Excel — DÙNG CHUNG cho các màn báo cáo đơn vị.
   Tải mẫu → chọn file → XEM TRƯỚC (đánh dấu dòng lỗi / tạo mới / ghi đè) → Xác nhận mới ghi. */

import { DownloadOutlined, UploadOutlined } from "@ant-design/icons";
import { Alert, Button, Modal, Table, Tag, Upload, message } from "antd";
import { useState } from "react";

import {
  type ImportColumn, type ImportKind, type ImportPreview, type ImportRow, type Role,
  commitImport, downloadImportTemplate, previewImport,
} from "../../../../lib/unit-daily-client";

type Props = {
  kind: ImportKind;
  role: Role;
  label: string;               // tên biểu, hiện trong tiêu đề modal
  onDone?: () => void;         // ghi xong → nạp lại màn
};

/** Cột bảng xem trước — dùng NHÃN tiếng Việt của biểu mẫu (server trả về), không phải khoá thô.
    Nếu server phiên bản cũ chưa trả `columns` thì suy ra từ khoá của dòng — tránh trắng màn. */
function previewColumns(cols: ImportColumn[] | undefined, rows: ImportRow[]) {
  const skip = new Set(["_row", "_errors", "_action"]);
  const safe: ImportColumn[] = cols?.length
    ? cols
    : [...new Set(rows.flatMap((r) => Object.keys(r)))]
        .filter((k) => !skip.has(k))
        .map((k) => ({ key: k, title: k, unit: "" }));
  return [
    { title: "Dòng", dataIndex: "_row", width: 70 },
    {
      title: "Trạng thái", key: "_st", width: 130,
      render: (_: unknown, r: ImportRow) =>
        r._errors?.length
          ? <Tag color="red">Lỗi</Tag>
          : r._action === "update"
            ? <Tag color="orange">Ghi đè</Tag>
            : <Tag color="green">Tạo mới</Tag>,
    },
    ...safe.map((c) => ({
      title: c.unit ? `${c.title} (${c.unit})` : c.title,
      dataIndex: c.key, width: 140,
      render: (v: unknown) => (v == null || v === "" ? "—" : String(v)),
    })),
    {
      title: "Ghi chú", key: "_er",
      render: (_: unknown, r: ImportRow) =>
        r._errors?.length
          ? <span style={{ color: "#cf1322" }}>{r._errors.join("; ")}</span>
          : <span style={{ color: "var(--muted)" }}>Hợp lệ</span>,
    },
  ];
}

export default function ExcelImportBar({ kind, role, label, onDone }: Props) {
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);

  const onFile = async (file: File) => {
    setBusy(true);
    try {
      setPreview(await previewImport(role, kind, file));
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setBusy(false);
    }
    return false;      // chặn Upload tự gửi — mình tự gọi API
  };

  const confirm = async () => {
    if (!preview) return;
    setSaving(true);
    try {
      const r = await commitImport(role, kind, preview.rows);
      message.success(`Đã ghi ${r.saved} bản ghi${r.skipped ? ` · bỏ qua ${r.skipped} dòng lỗi` : ""}.`);
      (r.warnings ?? []).forEach((w) => message.warning(w, 6));
      setPreview(null);
      onDone?.();
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const okCount = preview?.summary.ok ?? 0;
  const errCount = preview?.summary.error ?? 0;

  return (
    <>
      <Button icon={<DownloadOutlined />} loading={busy}
              onClick={() => downloadImportTemplate(role, kind)
                .catch((e) => message.error((e as Error).message))}>
        Tải mẫu Excel
      </Button>
      <Upload accept=".xlsx" showUploadList={false} beforeUpload={onFile}>
        <Button icon={<UploadOutlined />} loading={busy}>Nhập từ Excel</Button>
      </Upload>

      <Modal open={!!preview} width={1000} destroyOnHidden
             title={`Xem trước — ${label}`}
             onCancel={() => setPreview(null)}
             okText={`Xác nhận ghi ${okCount} dòng`}
             okButtonProps={{ disabled: !okCount, loading: saving }}
             cancelText="Huỷ"
             onOk={confirm}>
        {preview && (
          <>
            <Alert
              style={{ marginBottom: 12 }}
              type={errCount ? "warning" : "success"}
              showIcon
              message={`Đọc được ${preview.summary.total} dòng: ${okCount} hợp lệ, ${errCount} lỗi.`}
              description={errCount
                ? "Dòng lỗi sẽ bị BỎ QUA khi ghi. Sửa lại file rồi nhập lại nếu cần."
                : "Dòng 'Ghi đè' sẽ thay số liệu đã có của đúng đơn vị/ngày đó."}
            />
            <Table
              size="small"
              rowKey="_row"
              dataSource={preview.rows}
              columns={previewColumns(preview.columns, preview.rows)}
              pagination={{ pageSize: 20, showSizeChanger: false }}
              scroll={{ x: "max-content", y: 380 }}
              rowClassName={(r) => (r._errors?.length ? "blt-row-error" : "")}
            />
          </>
        )}
      </Modal>
    </>
  );
}
