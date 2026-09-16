import { DiffOutlined, ReloadOutlined } from "@ant-design/icons";
import { App, Drawer, Modal, Segmented, Table, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";

import {
  type EditRequest, type EditRequestPaged, type EditRequestStatusFilter, EDIT_REQUEST_STATUS,
  cancelMyEditRequest, fetchMyEditRequests, statusMeta,
} from "../../../lib/edit-request-client";
import { useAuth } from "../../auth/AuthContext";
import EditRequestDiffTable from "../components/EditRequestDiffTable";
import EditRequestInfo from "../components/EditRequestInfo";
import { stampVN } from "../sections/support-format";
import "../edit-request.css";
import "../support.css";

const PAGE_SIZE = 20;
const EMPTY: EditRequestPaged = {
  items: [], total: 0, page: 1, page_size: PAGE_SIZE,
  counts: { pending: 0, approved: 0, rejected: 0, cancelled: 0 },
};

/** Nhắc đỏ: duyệt xong đã gỡ chốt → đơn vị phải xác nhận chốt lại. */
const unlockNote = (r: EditRequest) => (r.status === "approved" && r.unlocked?.length ? (
  <div className="form-note" style={{ fontSize: 12 }}>Chốt số liệu đã được gỡ — vào xác nhận chốt lại</div>
) : null);

/** Đề nghị sửa số liệu — tài khoản đơn vị theo dõi các đề nghị đã gửi Ban duyệt. */
export default function MyEditRequestsPage() {
  const { message } = App.useApp();
  const { canEditUnitData } = useAuth();
  const [status, setStatus] = useState<EditRequestStatusFilter>("all");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<EditRequestPaged>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [active, setActive] = useState<EditRequest | null>(null);

  const load = useCallback(() => {
    setLoading(true); setErr("");
    fetchMyEditRequests({ status, page, page_size: PAGE_SIZE })
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [status, page]);
  useEffect(() => { load(); }, [load]);

  const cancel = (r: EditRequest) => {
    Modal.confirm({
      title: "Huỷ đề nghị này?",
      content: `${r.title} — Ban sẽ không xem xét đề nghị này nữa. Cần sửa thì gửi lại đề nghị mới.`,
      okText: "Huỷ đề nghị", okButtonProps: { danger: true }, cancelText: "Đóng",
      onOk: async () => {
        try {
          await cancelMyEditRequest(r.id);
          message.success("Đã huỷ đề nghị.");
          setActive(null);
          // Đang lọc "Chờ duyệt" mà huỷ dòng cuối của trang (không phải trang 1) → lùi một trang,
          // không thì bảng trống. Trang lùi tự tải lại qua `load` (phụ thuộc `page`).
          if (status === "pending" && data.items.length === 1 && page > 1) setPage(page - 1);
          else load();
        } catch (e) {
          message.error((e as Error).message);
        }
      },
    });
  };

  const c = data.counts;
  const allCount = c.pending + c.approved + c.rejected + c.cancelled;
  const options = [
    ...EDIT_REQUEST_STATUS.map((s) => ({ value: s.value, label: `${s.label} (${c[s.value]})` })),
    { value: "all", label: `Tất cả (${allCount})` },
  ];

  const columns = [
    { title: "Gửi lúc", key: "at", width: 140, render: (_: unknown, r: EditRequest) => stampVN(r.requested_at) },
    { title: "Đơn vị", dataIndex: "company", key: "company", width: 180 },
    {
      title: "Nội dung", key: "title",
      render: (_: unknown, r: EditRequest) => (
        <div className="er-title-cell">
          <span>{r.title}</span><small>{r.op_label}</small>{unlockNote(r)}
        </div>
      ),
    },
    { title: "Lý do", dataIndex: "reason", key: "reason", ellipsis: true },
    {
      title: "Trạng thái", key: "status", width: 110,
      render: (_: unknown, r: EditRequest) => <Tag color={statusMeta(r.status).color}>{statusMeta(r.status).label}</Tag>,
    },
    { title: "Ghi chú của Ban", dataIndex: "review_note", key: "note", ellipsis: true,
      render: (v: string | null) => v || "—" },
    {
      title: "", key: "act", width: 150,
      render: (_: unknown, r: EditRequest) => (r.status === "pending" && canEditUnitData ? (
        <button className="btn er-nowrap" onClick={(e) => { e.stopPropagation(); cancel(r); }}>Huỷ đề nghị</button>
      ) : null),
    },
  ];

  return (
    <div className="main er-page">
      <div className="page-title">
        <div>
          <h2><DiffOutlined style={{ marginRight: 8 }} />Đề nghị sửa số liệu</h2>
          <p>
            Số liệu ngày cũ đã khoá (quá hạn sửa hoặc đã chốt) chỉ đổi được khi Ban duyệt. Muốn sửa, mở đúng
            bản ghi cần sửa và bấm <b>Đề nghị sửa</b>. Kết quả duyệt được gửi qua email.
          </p>
        </div>
        <div className="actions">
          <button className="btn" onClick={load}><ReloadOutlined /> Tải lại</button>
        </div>
      </div>

      {err && <div className="blt-error">{err}</div>}

      <div className="card sp-row">
        <Segmented value={status} options={options}
          onChange={(v) => { setStatus(v as EditRequestStatusFilter); setPage(1); }} />
      </div>

      <div className="card">
        <Table<EditRequest>
          rowKey="id" size="small" columns={columns} dataSource={data.items} loading={loading}
          scroll={{ x: 960 }}
          locale={{ emptyText: "Chưa có đề nghị nào." }}
          onRow={(r) => ({ onClick: () => setActive(r), style: { cursor: "pointer" } })}
          pagination={{
            current: page, pageSize: PAGE_SIZE, total: data.total, showSizeChanger: false,
            onChange: setPage, hideOnSinglePage: true,
            showTotal: (t) => `${t} đề nghị`,
          }}
        />
      </div>

      <Drawer open={Boolean(active)} width="min(760px, 100vw)" onClose={() => setActive(null)}
        title={active ? active.title : ""}
        extra={active?.status === "pending" && canEditUnitData ? (
          <button className="btn er-nowrap" onClick={() => cancel(active)}>Huỷ đề nghị</button>
        ) : null}>
        {active && (
          <div className="er-section">
            <EditRequestInfo request={active} />
            <h3>Nội dung đề nghị (so với lúc gửi)</h3>
            <EditRequestDiffTable request={active} />
          </div>
        )}
      </Drawer>
    </div>
  );
}
