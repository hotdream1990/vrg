import { FileSearchOutlined, ReloadOutlined } from "@ant-design/icons";
import { Input, Segmented, Select, Table, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  type EditRequest, type EditRequestOp, type EditRequestPaged, type EditRequestStatusFilter,
  EDIT_REQUEST_OPS, EDIT_REQUEST_STATUS, fetchEditRequests, statusMeta,
} from "../../../lib/edit-request-client";
import { listUnits } from "../../../lib/member-unit-client";
import { stampVN } from "../sections/support-format";
import "../edit-request.css";
import "../support.css";

const PAGE_SIZE = 20;
const EMPTY: EditRequestPaged = {
  items: [], total: 0, page: 1, page_size: PAGE_SIZE,
  counts: { pending: 0, approved: 0, rejected: 0, cancelled: 0 },
};

/** Duyệt đề nghị sửa số liệu — danh sách phía Ban (quyền `edit_request`), mặc định lọc Chờ duyệt. */
export default function EditRequestReviewListPage() {
  const nav = useNavigate();
  const [status, setStatus] = useState<EditRequestStatusFilter>("pending");
  const [company, setCompany] = useState("");
  const [op, setOp] = useState<EditRequestOp | "">("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<EditRequestPaged>(EMPTY);
  const [units, setUnits] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    listUnits(true).then((rows) => setUnits(rows.map((u) => u.name))).catch(() => setUnits([]));
  }, []);

  const load = useCallback(() => {
    setLoading(true); setErr("");
    fetchEditRequests({ status, company, op, q, page, page_size: PAGE_SIZE })
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [status, company, op, q, page]);
  useEffect(() => { load(); }, [load]);

  /** Đổi bộ lọc là quay về trang 1. */
  const filter = <T,>(setter: (v: T) => void) => (v: T) => { setter(v); setPage(1); };

  const c = data.counts;
  const statusOptions = [
    ...EDIT_REQUEST_STATUS.map((s) => ({ value: s.value, label: `${s.label} (${c[s.value]})` })),
    { value: "all", label: `Tất cả (${c.pending + c.approved + c.rejected + c.cancelled})` },
  ];

  const columns = [
    { title: "Gửi lúc", key: "at", width: 140, render: (_: unknown, r: EditRequest) => stampVN(r.requested_at) },
    { title: "Đơn vị", dataIndex: "company", key: "company", width: 180 },
    {
      title: "Nội dung", key: "title",
      render: (_: unknown, r: EditRequest) => (
        <div className="er-title-cell"><span>{r.title}</span><small>{r.op_label}</small></div>
      ),
    },
    { title: "Lý do", dataIndex: "reason", key: "reason", ellipsis: true },
    { title: "Người gửi", key: "by", width: 160,
      render: (_: unknown, r: EditRequest) => r.requested_by_name || r.requested_by },
    {
      title: "Trạng thái", key: "status", width: 110,
      render: (_: unknown, r: EditRequest) => <Tag color={statusMeta(r.status).color}>{statusMeta(r.status).label}</Tag>,
    },
  ];

  return (
    <div className="main er-page">
      <div className="page-title">
        <div>
          <h2><FileSearchOutlined style={{ marginRight: 8 }} />Duyệt đề nghị sửa số liệu</h2>
          <p>
            Đơn vị thành viên đề nghị sửa số liệu ngày đã khoá (quá hạn sửa hoặc đã chốt). Duyệt thì hệ thống
            mới ghi vào số liệu thật và gỡ chốt của đơn vị từ ngày bị sửa; từ chối phải ghi rõ lý do.
          </p>
        </div>
        <div className="actions">
          <button className="btn" onClick={load}><ReloadOutlined /> Tải lại</button>
        </div>
      </div>

      {err && <div className="blt-error">{err}</div>}

      <div className="card sp-row">
        <Segmented value={status} options={statusOptions}
          onChange={(v) => filter<EditRequestStatusFilter>(setStatus)(v as EditRequestStatusFilter)} />
        <Select showSearch allowClear style={{ minWidth: 220 }} placeholder="Lọc theo đơn vị"
          value={company || undefined} onChange={(v) => filter(setCompany)(v ?? "")}
          options={units.map((u) => ({ value: u, label: u }))} />
        <Select allowClear style={{ minWidth: 200 }} placeholder="Loại số liệu"
          value={op || undefined} onChange={(v) => filter<EditRequestOp | "">(setOp)(v ?? "")}
          options={EDIT_REQUEST_OPS} />
        <Input.Search allowClear style={{ maxWidth: 300 }} placeholder="Tìm đơn vị, nội dung, lý do…"
          onSearch={filter(setQ)} />
      </div>

      <div className="card">
        <Table<EditRequest>
          rowKey="id" size="small" columns={columns} dataSource={data.items} loading={loading}
          scroll={{ x: 900 }}
          locale={{ emptyText: status === "pending" ? "Không có đề nghị nào đang chờ duyệt." : "Không có đề nghị nào." }}
          onRow={(r) => ({ onClick: () => nav(`/duyet-de-nghi-sua/${r.id}`), style: { cursor: "pointer" } })}
          pagination={{
            current: page, pageSize: PAGE_SIZE, total: data.total, showSizeChanger: false,
            onChange: setPage, hideOnSinglePage: true,
            showTotal: (t) => `${t} đề nghị`,
          }}
        />
      </div>
    </div>
  );
}
