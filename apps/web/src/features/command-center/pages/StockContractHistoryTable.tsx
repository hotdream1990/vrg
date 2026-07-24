/* Bảng Thống kê hợp đồng — CHỈ ĐỌC. Không dùng bảng 2-hàng của StockContractTable (nhập liệu);
   đây là danh sách tra cứu nên 1 hợp đồng = 1 dòng, có phân trang + dòng Tổng cộng. */

import { FileTextOutlined } from "@ant-design/icons";
import { Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";

import { type Role, type StockContract, openContractFile } from "../../../lib/unit-daily-client";
import { lineRevenueVnd, stockTonnesTotal } from "../../../lib/unit-daily-consumption";
import { dmy } from "../../../lib/date";
import { fmtNum } from "../../../lib/unit-daily-fields";

type Props = {
  role: Role;
  rows: StockContract[];
  showCompany: boolean;
  loading?: boolean;
};

const priceCell = (r: StockContract): string => {
  if (r.price == null) return "—";
  const ccy = r.ccy ?? "VND";
  const unit = ccy === "USD" ? "USD/tấn" : "triệu đ/tấn";
  const fx = ccy === "USD" && r.fx != null ? ` (tỷ giá ${fmtNum(r.fx, 0)})` : "";
  return `${fmtNum(r.price, 2)} ${unit}${fx}`;
};

export default function StockContractHistoryTable({ role, rows, showCompany, loading }: Props) {
  const columns: ColumnsType<StockContract> = [
    ...(showCompany ? [{ title: "Đơn vị", dataIndex: "company", key: "company", width: 170 }] : []),
    { title: "Số HĐ/PL", dataIndex: "code", key: "code", render: (v: string | null) => v || "—" },
    { title: "Chủng loại", dataIndex: "grade", key: "grade" },
    { title: "SL (tấn)", dataIndex: "qty", key: "qty", align: "right",
      render: (v: number | null) => fmtNum(v, 2) },
    { title: "Đơn giá", key: "price", render: (_v, r) => priceCell(r) },
    { title: "Bắt đầu tồn kho", dataIndex: "start_date", key: "start_date",
      render: (v: string) => dmy(v) },
    { title: "Lịch giao", dataIndex: "delivery_date", key: "delivery_date",
      render: (v: string | null) => dmy(v) },
    { title: "Ngày giao thực tế", dataIndex: "delivered_date", key: "delivered_date",
      render: (v: string | null) => dmy(v) },
    { title: "Trạng thái", key: "status", render: (_v, r) => (
      r.delivered_date ? <Tag color="green">Đã giao</Tag> : <Tag color="gold">Chưa giao</Tag>
    ) },
    { title: "HĐ scan", key: "file", render: (_v, r) => (
      r.file
        ? <a onClick={() => openContractFile(role, r.file!)} style={{ cursor: "pointer" }}>
            <FileTextOutlined /> {(r.filename ?? "file").slice(0, 20)}
          </a>
        : <span style={{ color: "var(--muted)" }}>—</span>
    ) },
  ];

  const totalQty = stockTonnesTotal(rows);
  const totalRevenueVnd = rows.reduce((a, r) => a + (lineRevenueVnd(r) ?? 0), 0);
  const qtyIdx = showCompany ? 3 : 2;
  const tailIdx = qtyIdx + 1;

  return (
    <div className="card" style={{ padding: 0 }}>
      <Table<StockContract>
        rowKey="id" columns={columns} dataSource={rows} loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `${t} hợp đồng` }}
        scroll={{ x: true }}
        summary={() => (!rows.length ? null : (
          <Table.Summary.Row style={{ fontWeight: 600, background: "rgba(125,125,125,.08)" }}>
            <Table.Summary.Cell index={0} colSpan={qtyIdx}>Tổng cộng</Table.Summary.Cell>
            <Table.Summary.Cell index={qtyIdx} align="right">{fmtNum(totalQty, 2)}</Table.Summary.Cell>
            <Table.Summary.Cell index={tailIdx} colSpan={6}>
              {totalRevenueVnd > 0 ? `Thành tiền quy VND: ${fmtNum(totalRevenueVnd / 1_000_000, 1)} triệu đ` : ""}
            </Table.Summary.Cell>
          </Table.Summary.Row>
        ))}
      />
    </div>
  );
}
