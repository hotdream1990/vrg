import { Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";

import { type AccessEntry, type AccessFilters, fetchAccessLog } from "../../../lib/access-log-client";
import { stampVN } from "../../../lib/date";
import { ROLE_COLOR, ROLE_LABEL } from "../../../lib/roles";

const PAGE_SIZE = 50;

const EVENT_COLOR: Record<string, string> = {
  login: "green", login_failed: "red", page: "blue",
};

const COLUMNS: ColumnsType<AccessEntry> = [
  { title: "Thời điểm", dataIndex: "at", width: 160, render: stampVN },
  {
    title: "Tài khoản", key: "user", width: 230,
    render: (_, r) => (
      <div style={{ lineHeight: 1.45 }}>
        <div style={{ fontWeight: 600 }}>{r.username}</div>
        {r.role && <Tag color={ROLE_COLOR[r.role]}>{ROLE_LABEL[r.role] ?? r.role}</Tag>}
        {r.company && <div style={{ fontSize: 12, color: "var(--muted)" }}>{r.company}</div>}
        {r.on_behalf && (
          <div style={{ fontSize: 12, color: "#b45309" }}>Do <b>{r.on_behalf}</b> đăng nhập hộ</div>
        )}
      </div>
    ),
  },
  {
    title: "Sự kiện", dataIndex: "event", width: 135,
    render: (_, r) => <Tag color={EVENT_COLOR[r.event] ?? "default"}>{r.event_label}</Tag>,
  },
  {
    title: "Trang", key: "page",
    render: (_, r) => (
      <div style={{ lineHeight: 1.45 }}>
        <div>{r.label}</div>
        <div style={{ fontSize: 12, color: "var(--muted)", wordBreak: "break-all" }}>{r.path}</div>
      </div>
    ),
  },
  { title: "IP", dataIndex: "ip", width: 140 },
];

/** Tab "Chi tiết": từng lượt đăng nhập / vào trang, mới nhất trước.
 *  `page` do MÀN CHA giữ (cùng chỗ với bộ lọc) — đổi bộ lọc là về trang 1 trong cùng một lần
 *  cập nhật state, nên không có cảnh bắn thừa một lượt gọi với số trang cũ. */
export default function AccessDetailTable({ filters, page, onPage, onError }: {
  filters: AccessFilters;
  page: number;
  onPage: (page: number) => void;
  onError: (msg: string) => void;
}) {
  const [data, setData] = useState<{ items: AccessEntry[]; total: number }>({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchAccessLog({ ...filters, page, page_size: PAGE_SIZE })
      .then((res) => setData({ items: res.items, total: res.total }))
      .catch((e) => onError(e instanceof Error ? e.message : "Lỗi tải lịch sử"))
      .finally(() => setLoading(false));
  }, [filters, page, onError]);

  return (
    <Table<AccessEntry>
      rowKey="id" size="small" columns={COLUMNS} dataSource={data.items} loading={loading}
      scroll={{ x: 900 }}
      pagination={{
        current: page, pageSize: PAGE_SIZE, total: data.total, showSizeChanger: false,
        onChange: onPage,
        showTotal: (t, [from, to]) => `${from}–${to} / ${t} lượt`,
      }}
      locale={{ emptyText: "Không có lượt truy cập nào khớp bộ lọc." }}
    />
  );
}
