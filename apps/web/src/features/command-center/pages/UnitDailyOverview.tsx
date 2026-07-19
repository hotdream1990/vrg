/* Lưới TỔNG HỢP toàn đơn vị của 1 ngày + dòng Tổng cộng (gộp cột tấn/tỷ đồng). Cột giữ đúng thứ tự
   Excel (cột suy ra xen giữa). Bấm "Sửa" mở form nhập của đơn vị đó. Realtime theo ngày. */

import { EditOutlined } from "@ant-design/icons";
import { Button, Empty, Table, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";

import { dmy } from "../../../lib/date";
import { dataColumns } from "../../../lib/unit-daily-columns";
import type { DayData, UnitPurchasePrice } from "../../../lib/unit-daily-client";
import { COLUMNS, type Column, type Kind, type Values, colValue, fmtNum, isSummable, toDisplay } from "../../../lib/unit-daily-fields";

type Row = { company: string; fields: Values; prices?: UnitPurchasePrice; updated_at?: string; updated_by?: string | null };

export default function UnitDailyOverview(
  { kind, data, canEdit, onEdit }: { kind: Kind; data: DayData; canEdit: boolean; onEdit: (asOf: string, company: string) => void },
) {
  const rows: Row[] = data.units.map((u) => {
    const e = data.entries[u];
    return { company: u, fields: e?.fields ?? {}, prices: data.prices?.[u], updated_at: e?.updated_at, updated_by: e?.updated_by };
  });

  const columns: ColumnsType<Row> = [
    { title: "Đơn vị", dataIndex: "company", key: "company", fixed: "left", width: 180, render: (c: string) => <b>{c}</b> },
    ...dataColumns<Row>(kind, data.plans),
    { title: "Cập nhật", key: "updated", fixed: "right", width: 116, align: "center",
      render: (_: unknown, r: Row) =>
        r.updated_at ? (
          <Tooltip title={r.updated_by ? `bởi ${r.updated_by}` : ""}>
            <span style={{ fontSize: 12 }}>{dmy(r.updated_at)}</span>
          </Tooltip>
        ) : <span style={{ opacity: 0.4 }}>—</span> },
    { title: "", key: "act", fixed: "right", width: 74, align: "center",
      render: (_: unknown, r: Row) => (
        <Button size="small" type="link" icon={<EditOutlined />} onClick={() => onEdit(data.as_of, r.company)}>
          {canEdit ? "Sửa" : "Xem"}
        </Button>
      ) },
  ];

  if (!data.units.length) return <Empty description="Chưa có đơn vị thành viên nào" />;

  // Dòng Tổng cộng: gộp cột dòng chảy (tấn/tỷ đồng) theo ĐÚNG thứ tự leaf = COLUMNS[kind]; giá/% để trống.
  const rollup = (c: Column): string => {
    if (!isSummable(c.unit)) return "";
    const total = rows.reduce((a, r) => a + (colValue(kind, c.key, r.fields, data.plans[r.company]) ?? 0), 0);
    return fmtNum(toDisplay(c, total), 2);
  };

  return (
    <Table<Row>
      rowKey="company"
      size="small"
      columns={columns}
      dataSource={rows}
      pagination={false}
      scroll={{ x: "max-content", y: 560 }}
      bordered
      summary={() => (
        <Table.Summary fixed>
          <Table.Summary.Row>
            <Table.Summary.Cell index={0}><b>Tổng cộng</b></Table.Summary.Cell>
            {COLUMNS[kind].map((c, i) => (
              <Table.Summary.Cell key={c.key} index={i + 1} align="right"><b>{rollup(c)}</b></Table.Summary.Cell>
            ))}
            <Table.Summary.Cell index={COLUMNS[kind].length + 1} colSpan={2} />
          </Table.Summary.Row>
        </Table.Summary>
      )}
    />
  );
}
