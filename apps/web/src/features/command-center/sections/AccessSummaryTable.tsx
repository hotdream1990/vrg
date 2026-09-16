import { Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";

import {
  type AccessFilters,
  type AccessSummary,
  type AccessSummaryRow,
  type AccessTopPage,
  fetchAccessSummary,
} from "../../../lib/access-log-client";
import { stampVN } from "../../../lib/date";
import { ROLE_COLOR, ROLE_LABEL } from "../../../lib/roles";

const EMPTY: AccessSummary = { items: [], top_pages: [] };

//: Danh sách nay gồm CẢ tài khoản chưa truy cập lần nào nên dài hơn hẳn → phải phân trang.
const PAGE_SIZE = 25;

const SUMMARY_COLUMNS: ColumnsType<AccessSummaryRow> = [
  {
    title: "Tài khoản", key: "username", width: 240, fixed: "left",
    render: (_, r) => (
      <div style={{ lineHeight: 1.45 }}>
        <div style={{ fontWeight: 600 }}>{r.username}</div>
        {r.role && <Tag color={ROLE_COLOR[r.role]}>{ROLE_LABEL[r.role] ?? r.role}</Tag>}
        {r.company && <div style={{ fontSize: 12, color: "var(--muted)" }}>{r.company}</div>}
        {/* Tài khoản đã cấp mà chưa dùng bao giờ — thứ quản trị cần thấy ngay, không phải suy ra
            từ một hàng toàn dấu gạch ngang. */}
        {!r.last_seen && (
          <div style={{ fontSize: 12, color: "var(--danger)" }}>Chưa truy cập lần nào</div>
        )}
      </div>
    ),
  },
  {
    title: "Đăng nhập gần nhất", dataIndex: "last_login", width: 165,
    render: (v: string | null) => stampVN(v),
  },
  {
    title: "Hoạt động gần nhất", dataIndex: "last_seen", width: 165,
    render: (v: string | null) => stampVN(v),
  },
  {
    title: "Số lần đăng nhập", key: "logins", width: 130, align: "right",
    render: (_, r) => (
      <span>
        {r.logins}
        {r.failed_logins > 0 && (
          <span style={{ color: "var(--danger)", fontSize: 12 }}> · sai {r.failed_logins}</span>
        )}
      </span>
    ),
  },
  {
    // Gộp "số lượt" và "số trang khác nhau" vào một cột: bảng đủ chỗ hiện cột quan trọng nhất
    // (trang hay vào nhất) mà không phải cuộn ngang. Excel vẫn tách riêng từng con số.
    title: "Lượt xem trang", key: "page_views", width: 150, align: "right",
    render: (_, r) => (
      <span>
        {r.page_views}
        <span style={{ color: "var(--muted)", fontSize: 12 }}> / {r.distinct_pages} trang</span>
      </span>
    ),
  },
  { title: "Số ngày hoạt động", dataIndex: "active_days", width: 130, align: "right" },
  {
    title: "Trang hay vào nhất", key: "top_page",
    render: (_, r) => r.top_page
      ? <span>{r.top_page} <span style={{ color: "var(--muted)" }}>({r.top_page_views} lượt)</span></span>
      : <span style={{ color: "var(--muted)" }}>—</span>,
  },
];

const TOP_COLUMNS: ColumnsType<AccessTopPage> = [
  { title: "Trang", dataIndex: "label" },
  { title: "Lượt xem", dataIndex: "views", width: 110, align: "right" },
  { title: "Số người vào", dataIndex: "users", width: 130, align: "right" },
];

/** Tab "Theo tài khoản": mỗi người 1 dòng — dùng nhiều hay ít, lần cuối vào lúc nào, hay vào trang gì. */
export default function AccessSummaryTable({ filters, onError }: {
  filters: AccessFilters;
  onError: (msg: string) => void;
}) {
  const [data, setData] = useState<AccessSummary>(EMPTY);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchAccessSummary(filters)
      .then(setData)
      .catch((e) => onError(e instanceof Error ? e.message : "Lỗi tải tổng hợp"))
      .finally(() => setLoading(false));
  }, [filters, onError]);

  return (
    <>
      <Table<AccessSummaryRow>
        rowKey="username" size="small" columns={SUMMARY_COLUMNS} dataSource={data.items}
        loading={loading} scroll={{ x: 1050 }}
        pagination={{
          pageSize: PAGE_SIZE, showSizeChanger: false,
          showTotal: (t, [from, to]) => `${from}–${to} / ${t} tài khoản`,
        }}
        locale={{ emptyText: "Không có tài khoản nào khớp bộ lọc." }}
      />
      <h4 style={{ margin: "20px 0 8px" }}>Trang được xem nhiều nhất</h4>
      <Table<AccessTopPage>
        rowKey="path" size="small" columns={TOP_COLUMNS} dataSource={data.top_pages}
        loading={loading} pagination={false}
        locale={{ emptyText: "Chưa có lượt xem trang nào." }}
      />
    </>
  );
}
