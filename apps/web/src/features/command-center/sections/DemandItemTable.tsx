import { CopyOutlined, DeleteOutlined, EditOutlined, FormOutlined } from "@ant-design/icons";
import { Button, Popconfirm, Table, Tag, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";

import { dmy } from "../../../lib/date";
import type { DemandItem } from "../../../lib/market-demand-client";
import { demandLabel, fmtPrice, fmtQty, shortUnit } from "../../../lib/market-demand-meta";

const PAGE_SIZE = 20;
// Ghi chú dài (nhất là nguyên văn bản cũ) chỉ hiện 2 dòng; đủ nội dung ở tooltip.
const CLAMP_2 = {
  display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
} as const;

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
        title: "Đơn vị", dataIndex: "company", width: 130,
        render: (v: string) => <Tooltip title={v}>{shortUnit(v)}</Tooltip>,
      } as const]
      : []),
    { title: "Khách hàng", dataIndex: "customer", width: 160 },
    { title: "Chủng loại", dataIndex: "grade", width: 100 },
    { title: "Số lượng", key: "qty", width: 90, align: "right", render: (_, r) => fmtQty(r) },
    { title: "Đơn giá", key: "price", width: 115, align: "right", render: (_, r) => fmtPrice(r) },
    // Nơi giao + thời gian giao chung một cột (2 dòng) cho bảng vừa màn laptop.
    { title: "Giao hàng", key: "delivery", width: 150, render: (_, r) => <DeliveryCell item={r} /> },
    // Kết quả là cột người xem cần nhất → đủ rộng và xuống dòng, không cắt chữ.
    {
      title: "Kết quả", dataIndex: "result", width: 190,
      render: (v: string) => <span style={{ whiteSpace: "pre-line" }}>{v || "—"}</span>,
    },
    {
      title: "Ghi chú", dataIndex: "note", width: 150,
      render: (_, r) => <NoteCell item={r} />,
    },
    ...(showActions
      ? [{
        title: "Thao tác", key: "actions", width: 120, fixed: "right" as const,
        render: (_: unknown, r: DemandItem) => (
          <RowActions item={r} perm={perm(r)} onEdit={onEdit} onClone={onClone} onDelete={onDelete} />
        ),
      }]
      : []),
  ];
  // Cuộn ngang đúng bằng tổng bề rộng cột (~1.170px, vừa khung màn 1600px): khung hẹp hơn thì bảng
  // cuộn, cột Thao tác ghim phải nên không bị đẩy ra ngoài.
  const scrollX = columns.reduce((t, c) => t + (typeof c.width === "number" ? c.width : 0), 0);

  return (
    <Table<DemandItem>
      rowKey="id" size="small" columns={columns} dataSource={items} loading={loading}
      scroll={{ x: scrollX }}
      locale={{ emptyText: "Chưa có nhu cầu nào trong khoảng này." }}
      pagination={{
        pageSize: PAGE_SIZE, showSizeChanger: false, hideOnSinglePage: true,
        showTotal: (t) => `${t} phiếu`,
      }}
    />
  );
}

function DeliveryCell({ item }: { item: DemandItem }) {
  if (!item.delivery_place && !item.delivery_time) return <>—</>;
  return (
    <div>
      <div>{item.delivery_place || "—"}</div>
      {item.delivery_time && (
        <div style={{ color: "var(--muted)", fontSize: 12 }}>{item.delivery_time}</div>
      )}
    </div>
  );
}

function NoteCell({ item }: { item: DemandItem }) {
  const body = (
    <div style={CLAMP_2}>
      {item.legacy && <Tag style={{ fontSize: 11, marginRight: 6 }}>Chuyển từ bản cũ</Tag>}
      {item.note || "—"}
    </div>
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
        <Tooltip title={perm.locked ? "Cập nhật kết quả, ghi chú" : "Sửa"}>
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
