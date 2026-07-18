/* Hiển thị artifact do Trợ lý AI trả về: bảng (antd Table) hoặc biểu đồ đường (MultiLineChart). */

import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { ChatArtifact } from "../../../lib/assistant-client";
import MultiLineChart from "../charts/MultiLineChart";

const fmt = (v: unknown): string => {
  if (v == null || v === "") return "—";
  if (typeof v === "number") return v.toLocaleString("vi-VN", { maximumFractionDigits: 2 });
  return String(v);
};

export default function AssistantArtifact({ art }: { art: ChatArtifact }) {
  if (art.type === "line") {
    return (
      <div style={{ margin: "8px 0" }}>
        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>{art.title}</div>
        <div style={{ height: 260 }}>
          <MultiLineChart labels={art.labels} series={art.series} />
        </div>
      </div>
    );
  }
  const columns: ColumnsType<Record<string, unknown>> = art.columns.map((c, i) => ({
    title: c.label,
    dataIndex: c.key,
    key: c.key,
    align: i === 0 ? "left" : "right",
    render: (v: unknown) => fmt(v),
  }));
  const rows = art.rows.map((r, i) => ({ ...r, _k: i }));
  return (
    <div style={{ margin: "8px 0" }}>
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>{art.title}</div>
      <Table
        rowKey="_k"
        size="small"
        bordered
        columns={columns}
        dataSource={rows}
        pagination={false}
        scroll={{ x: "max-content" }}
      />
    </div>
  );
}
