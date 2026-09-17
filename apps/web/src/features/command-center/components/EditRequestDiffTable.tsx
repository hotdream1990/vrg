import { PaperClipOutlined } from "@ant-design/icons";
import { App, Empty, Table } from "antd";
import { useMemo } from "react";

import type { EditRequest } from "../../../lib/edit-request-client";
import { openEditRequestFile } from "../../../lib/edit-request-client";
import { type DiffRow, buildEditRequestDiff, displayValue, isFileLeaf } from "../../../lib/edit-request-diff";

type Props = {
  request: Pick<EditRequest, "id" | "op" | "payload" | "before">;
  /** Có = trang duyệt, hiện thêm cột "Hiện tại". */
  current?: Record<string, unknown> | null;
  withCurrent?: boolean;
  /** Mở file qua endpoint của Ban (chỉ trang duyệt có quyền). Không bật = chỉ hiện tên file. */
  canOpenFiles?: boolean;
  /** Nhãn server tra sẵn cho trang duyệt (id khách → tên khách…). Màn đơn vị không có. */
  labels?: Record<string, Record<string, string>>;
};

/** Bảng trước/sau của một đề nghị — CHỈ các ô có khác biệt; ô đề nghị khác hiện tại được tô nổi. */
export default function EditRequestDiffTable({ request, current, withCurrent = false, canOpenFiles = false, labels }: Props) {
  const { message } = App.useApp();
  const rows = useMemo(
    () => buildEditRequestDiff(request, current, withCurrent),
    [request, current, withCurrent],
  );
  const isDelete = request.op.endsWith("_delete");

  const cell = (path: string, v: unknown, emptyText = "(trống)") => {
    if (isFileLeaf(v)) {
      if (!canOpenFiles) return <span><PaperClipOutlined /> {v.filename}</span>;
      return (
        <a role="button" tabIndex={0}
          onClick={() => openEditRequestFile(request.id, v).catch((e) => message.error((e as Error).message))}>
          <PaperClipOutlined /> {v.filename}
        </a>
      );
    }
    const text = displayValue(v, path, labels);
    return text === "(trống)" ? <span style={{ color: "var(--muted)" }}>{emptyText}</span> : text;
  };

  const columns = [
    { title: "Ô số liệu", dataIndex: "label", key: "label", width: "34%" },
    { title: "Lúc gửi", key: "before", render: (_: unknown, r: DiffRow) => cell(r.path, r.before) },
    ...(withCurrent
      ? [{ title: "Hiện tại", key: "current", render: (_: unknown, r: DiffRow) => cell(r.path, r.current) }]
      : []),
    {
      title: "Đề nghị", key: "proposed",
      render: (_: unknown, r: DiffRow) => (
        <span style={r.highlight ? { fontWeight: 600, color: "#b45309" } : undefined}>
          {cell(r.path, r.proposed, isDelete ? "(xoá)" : "(trống)")}
        </span>
      ),
      onCell: (r: DiffRow) => ({ style: r.highlight ? { background: "#fef3c7" } : undefined }),
    },
  ];

  if (!rows.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Không có ô nào khác biệt." />;
  }
  return (
    <div style={{ overflowX: "auto" }}>
      <Table<DiffRow> rowKey="path" size="small" columns={columns} dataSource={rows}
        pagination={false} scroll={{ x: withCurrent ? 720 : 560 }} />
    </div>
  );
}
