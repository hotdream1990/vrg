import { CopyOutlined, DeleteOutlined, EditOutlined, FormOutlined } from "@ant-design/icons";
import { Button, Popconfirm, Table, Tag, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";

import { dmy } from "../../../lib/date";
import type { DemandItem } from "../../../lib/market-demand-client";
import {
  demandLabel, fmtDelivery, fmtPrice, fmtQty, shortUnit, statusMeta,
} from "../../../lib/market-demand-meta";

const PAGE_SIZE = 20;

/** Quyền trên TỪNG phiếu — màn cha tính (vai trò, cửa sổ sửa, đơn vị đã sáp nhập). */
export type DemandRowPerm = {
  edit: boolean;
  /** Ngày nhận đã ngoài cửa sổ sửa → tài khoản đơn vị gửi đề nghị để Ban duyệt. */
  request: boolean;
  clone: boolean;
  remove: boolean;
  /** Ngoài cửa sổ sửa: xoá sẽ thành đề nghị xoá. */
  locked: boolean;
};

type Props = {
  items: DemandItem[];
  loading: boolean;
  showCompany: boolean;
  /** Có ít nhất một nút ghi trên màn (lãnh đạo đơn vị / chuyên viên mức Xem: không có cột Thao tác). */
  showActions: boolean;
  perm: (i: DemandItem) => DemandRowPerm;
  onEdit: (i: DemandItem, request: boolean) => void;
  onClone: (i: DemandItem) => void;
  /** Không trả promise cho Popconfirm: xoá quá hạn mở hộp đề nghị, ô xác nhận phải đóng ngay. */
  onDelete: (i: DemandItem) => void;
};

/** Bảng phiếu nhu cầu thị trường — thứ tự giữ nguyên như server trả (ngày nhận mới trước). */
export default function DemandItemTable({
  items, loading, showCompany, showActions, perm, onEdit, onClone, onDelete,
}: Props) {
  const columns: ColumnsType<DemandItem> = [
    { title: "Ngày nhận", dataIndex: "as_of", width: 96, render: (v: string) => dmy(v) },
    ...(showCompany
      ? [{
        title: "Đơn vị", dataIndex: "company", width: 150,
        render: (v: string) => <Tooltip title={v}>{shortUnit(v)}</Tooltip>,
      } as const]
      : []),
    { title: "Khách hàng", dataIndex: "customer", width: 200 },
    { title: "Chủng loại", dataIndex: "grade", width: 120 },
    { title: "Số lượng", key: "qty", width: 100, align: "right", render: (_, r) => fmtQty(r) },
    { title: "Đơn giá", key: "price", width: 150, align: "right", render: (_, r) => fmtPrice(r) },
    // Tình trạng đứng ngay sau giá: là cột người xem cần nhất, không được rơi ra ngoài khung.
    { title: "Tình trạng", key: "status", width: 150, render: (_, r) => <StatusCell item={r} /> },
    { title: "Giao tại", dataIndex: "delivery_place", width: 140, render: (v: string) => v || "—" },
    {
      title: "Thời gian giao", key: "delivery", width: 160,
      render: (_, r) => fmtDelivery(r.delivery_from, r.delivery_to),
    },
    {
      title: "Ghi chú", dataIndex: "note", width: 240, ellipsis: { showTitle: false },
      render: (_, r) => <NoteCell item={r} />,
    },
    ...(showActions
      ? [{
        title: "Thao tác", key: "actions", width: 150, fixed: "right" as const,
        render: (_: unknown, r: DemandItem) => (
          <RowActions item={r} perm={perm(r)} onEdit={onEdit} onClone={onClone} onDelete={onDelete} />
        ),
      }]
      : []),
  ];

  return (
    <Table<DemandItem>
      rowKey="id" size="small" columns={columns} dataSource={items} loading={loading}
      scroll={{ x: showCompany ? 1660 : 1510 }}
      locale={{ emptyText: "Chưa có nhu cầu nào trong khoảng này." }}
      pagination={{
        pageSize: PAGE_SIZE, showSizeChanger: false, hideOnSinglePage: true,
        showTotal: (t) => `${t} phiếu`,
      }}
    />
  );
}

function StatusCell({ item }: { item: DemandItem }) {
  const s = statusMeta(item.status);
  return (
    <>
      <Tag color={s.color} style={{ margin: 0 }}>{s.label}</Tag>
      {item.status === "signed" && (
        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
          HĐ {item.contract_no || "—"} · {dmy(item.contract_date)}
        </div>
      )}
    </>
  );
}

function NoteCell({ item }: { item: DemandItem }) {
  const body = (
    <span>
      {item.legacy && <Tag style={{ fontSize: 11, marginRight: 6 }}>Chuyển từ bản cũ</Tag>}
      {item.note || "—"}
    </span>
  );
  if (!item.note) return body;
  return (
    <Tooltip placement="topRight" title={item.note}
      styles={{ root: { maxWidth: "min(520px, 80vw)" }, container: { whiteSpace: "pre-line" } }}>
      {body}
    </Tooltip>
  );
}

type ActionProps = Pick<Props, "onEdit" | "onClone" | "onDelete"> & { item: DemandItem; perm: DemandRowPerm };

function RowActions({ item, perm, onEdit, onClone, onDelete }: ActionProps) {
  return (
    <div style={{ display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap" }}>
      {perm.edit && (
        <Tooltip title={perm.locked ? "Cập nhật tình trạng, số hợp đồng, ngày ký, ghi chú" : "Sửa"}>
          <Button size="small" type="text" icon={<EditOutlined />} aria-label="Sửa"
            onClick={() => onEdit(item, false)} />
        </Tooltip>
      )}
      {perm.clone && (
        <Tooltip title="Nhân bản — tạo phiếu mới cùng nội dung">
          <Button size="small" type="text" icon={<CopyOutlined />} aria-label="Nhân bản"
            onClick={() => onClone(item)} />
        </Tooltip>
      )}
      {perm.remove && (
        <Popconfirm
          title="Xoá phiếu nhu cầu này?"
          description={perm.locked
            ? "Phiếu đã quá hạn sửa: hệ thống sẽ mở hộp gửi đề nghị xoá, Ban duyệt xong mới xoá thật."
            : demandLabel(item)}
          okText="Xoá" cancelText="Huỷ" okButtonProps={{ danger: true }}
          onConfirm={() => { onDelete(item); }}>
          <Tooltip title="Xoá">
            <Button size="small" type="text" danger icon={<DeleteOutlined />} aria-label="Xoá" />
          </Tooltip>
        </Popconfirm>
      )}
      {perm.request && (
        <Tooltip title="Ngày nhận đã ngoài thời hạn sửa — gửi đề nghị để Ban duyệt">
          <Button size="small" icon={<FormOutlined />} onClick={() => onEdit(item, true)}>
            Đề nghị sửa
          </Button>
        </Tooltip>
      )}
    </div>
  );
}
