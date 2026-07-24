import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { AuditEntry } from "../../../lib/audit-client";
import { type FieldChange, diffFields, fmtValue } from "../../../lib/audit-diff";
import { dmy } from "../../../lib/date";

const cell = (v: unknown, strike = false) => (
  <span style={{ textDecoration: strike ? "line-through" : undefined, color: strike ? "#a1a1aa" : undefined }}>
    {fmtValue(v)}
  </span>
);

const columnsFor = (action: string): ColumnsType<FieldChange> => [
  { title: "Ô số liệu", dataIndex: "label", width: 280,
    render: (label: string, r) => (
      <div style={{ lineHeight: 1.4 }}>
        <div>{label}</div>
        <div style={{ fontSize: 11, color: "var(--muted)" }}>{r.path}</div>
      </div>
    ) },
  { title: action === "delete" ? "Giá trị đã xoá" : "Trước", dataIndex: "from", width: 240,
    render: (v) => cell(v, action !== "delete") },
  ...(action === "delete" ? [] : [{
    title: action === "create" ? "Giá trị nhập vào" : "Sau", dataIndex: "to", width: 240,
    render: (v: unknown) => <b style={{ color: "#0a9e48" }}>{fmtValue(v)}</b>,
  }]),
];

/** Chi tiết 1 dòng nhật ký: liệt kê TỪNG ô đã đổi (trước → sau) + ngữ cảnh bản ghi. */
export default function AuditChangeDetail({ entry }: { entry: AuditEntry }) {
  const changes = diffFields(entry.before, entry.after);
  return (
    <div style={{ padding: "4px 0 8px" }}>
      <div style={{ marginBottom: 8, fontSize: 13, color: "var(--muted)" }}>
        Bản ghi: <b style={{ color: "#16241d" }}>{entry.entity_key || "—"}</b>
        {entry.as_of && <> · Ngày số liệu: <b style={{ color: "#16241d" }}>{dmy(entry.as_of)}</b></>}
        {entry.company && <> · Đơn vị: <b style={{ color: "#16241d" }}>{entry.company}</b></>}
        {entry.note && <> · {entry.note}</>}
      </div>
      {changes.length === 0 ? (
        <div className="scan-empty">Không có ô số liệu nào thay đổi (chỉ ghi nhận sự kiện).</div>
      ) : (
        <Table<FieldChange>
          rowKey="path" size="small" columns={columnsFor(entry.action)} dataSource={changes}
          pagination={changes.length > 20 ? { pageSize: 20, showSizeChanger: false } : false}
        />
      )}
    </div>
  );
}
