/* Bản nháp tờ trình giá sàn — danh sách (phân trang ở SERVER, không tải hết). Bản nháp tách hẳn biểu
   giá sàn chính thức: sửa/xoá ở đây không đụng số đã ban hành. Gác cap `floor_suggest`;
   Lãnh đạo Tập đoàn chỉ xem (ẩn Tạo/Xoá — server cũng chặn). */

import { BulbOutlined, DeleteOutlined, EditOutlined, FormOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, App, Button, Popconfirm, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  DRAFT_SOURCE_LABEL, type DraftSource, type DraftSummary, createDraft, deleteDraft, draftPath, listDrafts,
} from "../../../lib/floor-proposal-client";
import { dmy, stampVN } from "../../../lib/date";
import { useAuth } from "../../auth/AuthContext";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";

const PAGE_SIZE = 20;
const SOURCE_COLOR: Record<DraftSource, string> = { assistant: "purple", floor_suggest: "green", manual: "blue" };

const errText = (e: unknown) => (e instanceof Error ? e.message : "Có lỗi xảy ra, vui lòng thử lại.");

export default function FloorDraftListPage() {
  const { canEditCap } = useAuth();
  const { message } = App.useApp();
  const navigate = useNavigate();
  const canEdit = canEditCap("floor_suggest");

  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ items: DraftSummary[]; total: number }>({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [err, setErr] = useState("");

  // Đổi trang nhanh: chỉ nhận kết quả của lần gọi MỚI NHẤT, lần cũ về sau bị bỏ.
  const seq = useRef(0);
  const load = useCallback(() => {
    const mine = ++seq.current;
    setLoading(true); setErr("");
    listDrafts(page, PAGE_SIZE)
      .then((r) => { if (mine === seq.current) setData({ items: r.items, total: r.total }); })
      .catch((e) => { if (mine === seq.current) setErr(errText(e)); })
      .finally(() => { if (mine === seq.current) setLoading(false); });
  }, [page]);
  useEffect(() => { load(); }, [load]);

  const createNew = async () => {
    setCreating(true);
    try {
      const d = await createDraft({ source: "manual" });
      navigate(draftPath(d.id));
    } catch (e) {
      message.error(errText(e));
    } finally {
      setCreating(false);
    }
  };

  const remove = async (id: number) => {
    try {
      await deleteDraft(id);
      message.success("Đã xoá bản nháp.");
      // Xoá dòng cuối cùng của trang > 1 → lùi một trang, khỏi đứng trên trang trống.
      if (data.items.length === 1 && page > 1) setPage(page - 1);
      else load();
    } catch (e) {
      message.error(errText(e));
    }
  };

  const columns: ColumnsType<DraftSummary> = [
    {
      title: "Tiêu đề", dataIndex: "title", ellipsis: true, width: 280,
      render: (v: string, r) => <Link to={draftPath(r.id)}>{v || `Bản nháp #${r.id}`}</Link>,
    },
    { title: "Ngày tờ trình", dataIndex: "as_of", width: 120, render: (v: string) => dmy(v) },
    { title: "Lần", dataIndex: "lan", width: 64, align: "center" },
    { title: "Mức nổi bật", dataIndex: "headline", width: 220, ellipsis: true,
      render: (v: string) => v || <span style={{ color: "var(--muted)" }}>—</span> },
    {
      title: "Nguồn", dataIndex: "source", width: 130,
      render: (v: DraftSource) => <Tag color={SOURCE_COLOR[v] ?? "default"}>{DRAFT_SOURCE_LABEL[v] ?? v}</Tag>,
    },
    { title: "Người sửa cuối", key: "by", width: 150, ellipsis: true,
      render: (_, r) => r.updated_by ?? r.created_by ?? "—" },
    { title: "Cập nhật lúc", dataIndex: "updated_at", width: 170, render: (v: string) => stampVN(v) },
    {
      title: "", key: "action", width: canEdit ? 130 : 80, align: "right",
      render: (_, r) => (
        <span style={{ whiteSpace: "nowrap" }}>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => navigate(draftPath(r.id))}>
            Mở
          </Button>
          {canEdit && (
            <Popconfirm title="Xoá bản nháp này?" description="Bản nháp đã xoá không khôi phục được."
              okText="Xoá" cancelText="Huỷ" okButtonProps={{ danger: true }} onConfirm={() => remove(r.id)}>
              <Button type="text" danger size="small" icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </span>
      ),
    },
  ];

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><FormOutlined style={{ marginRight: 8 }} />Bản nháp tờ trình giá sàn</h2>
          <p>Các phương án giá sàn đã lưu để sửa tiếp (số + đoạn diễn giải) và in tờ trình. Bản nháp không ghi vào
            biểu giá sàn chính thức.</p>
        </div>
      </div>
      <ReadOnlyNotice cap="floor_suggest" />
      {err && <Alert type="error" showIcon message={err} style={{ marginBottom: 12 }} />}

      <div className="card" style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        {canEdit && (
          <Button type="primary" icon={<PlusOutlined />} loading={creating} onClick={createNew}>
            Tạo bản nháp mới
          </Button>
        )}
        <Button icon={<BulbOutlined />} onClick={() => navigate("/goi-y-gia-san")}>Gợi ý giá sàn</Button>
        <Button icon={<ReloadOutlined />} style={{ marginLeft: "auto" }} onClick={load}>Tải lại</Button>
        {canEdit && (
          <div className="form-note" style={{ fontSize: 12.5, width: "100%" }}>
            "Tạo bản nháp mới" dựng phương án từ mức mô hình hôm nay. Có thể lập từ Trợ lý AI hoặc màn Gợi ý giá sàn.
          </div>
        )}
      </div>

      <div className="card" style={{ marginTop: 12 }}>
        <Table<DraftSummary>
          rowKey="id" size="small" columns={columns} dataSource={data.items} loading={loading}
          scroll={{ x: 1280 }}
          pagination={{
            current: page, pageSize: PAGE_SIZE, total: data.total, showSizeChanger: false,
            onChange: setPage,
            showTotal: (t, [from, to]) => `${from}–${to} / ${t} bản nháp`,
          }}
          locale={{ emptyText: "Chưa có bản nháp nào." }}
        />
      </div>
    </div>
  );
}
