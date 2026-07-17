/* Danh sách BÁO CÁO TUẦN dạng BẢNG theo dòng thời gian (ẩn tuần trống) — DÙNG CHUNG cho đơn vị
   thành viên (đơn vị được gán) và chuyên viên (mọi đơn vị). Mỗi dòng = 1 (tuần × đơn vị); cột số
   liệu giữ đúng thứ tự Excel; ô "Tuần" gộp cho các đơn vị cùng tuần. */

import { EditOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Empty, Table, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";

import { dmy } from "../../../lib/date";
import { dataColumns } from "../../../lib/unit-weekly-columns";
import {
  type Timeline, type TimelineRow, fetchMyWeeklyTimeline, fetchWeeklyTimeline,
} from "../../../lib/unit-weekly-client";
import type { Kind } from "../../../lib/unit-weekly-fields";
import { weekLabel } from "../../../lib/week";

const WEEKS = [8, 16, 26, 52];

type Row = TimelineRow & { key: string; _weekSpan: number };

type Props = {
  kind: Kind;
  role: "member" | "hq";
  isAdmin: boolean;
  refreshKey: number;
  onEdit: (week: string, company: string) => void;
  onAdd: () => void;
};

export default function UnitWeeklyTimeline({ kind, role, refreshKey, onEdit, onAdd }: Props) {
  const [weeks, setWeeks] = useState(16);
  const [data, setData] = useState<Timeline | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setLoading(true); setErr("");
    (role === "member" ? fetchMyWeeklyTimeline : fetchWeeklyTimeline)(kind, weeks)
      .then(setData).catch((e) => setErr(e.message)).finally(() => setLoading(false));
  }, [role, kind, weeks]);
  useEffect(() => { load(); }, [load, refreshKey]);

  // Rows theo thứ tự backend (tuần DESC, đơn vị); tính rowSpan gộp ô "Tuần".
  const rows = useMemo<Row[]>(() => {
    const es = data?.entries ?? [];
    const counts: Record<string, number> = {};
    es.forEach((e) => { counts[e.week_key] = (counts[e.week_key] ?? 0) + 1; });
    const seen = new Set<string>();
    return es.map((e) => {
      const span = seen.has(e.week_key) ? 0 : counts[e.week_key];
      seen.add(e.week_key);
      return { ...e, key: `${e.week_key}|${e.company}`, _weekSpan: span };
    });
  }, [data]);

  const columns: ColumnsType<Row> = [
    { title: "Tuần", key: "week", fixed: "left", width: 150,
      onCell: (r) => ({ rowSpan: r._weekSpan }),
      render: (_: unknown, r: Row) => <b style={{ color: "#0a9e48" }}>{weekLabel(r.week_key)}</b> },
    { title: "Đơn vị", dataIndex: "company", key: "company", fixed: "left", width: 170,
      render: (c: string) => <b>{c}</b> },
    ...dataColumns<Row>(kind, data?.plans ?? {}),
    { title: "Cập nhật", key: "updated", fixed: "right", width: 116, align: "center",
      render: (_: unknown, r: Row) => (
        <Tooltip title={r.updated_by ? `bởi ${r.updated_by}` : ""}>
          <span style={{ fontSize: 12 }}>{dmy(r.updated_at)}</span>
        </Tooltip>
      ) },
    { title: "", key: "act", fixed: "right", width: 66, align: "center",
      render: (_: unknown, r: Row) => (
        <Button size="small" type="link" icon={<EditOutlined />} onClick={() => onEdit(r.week_key, r.company)} />
      ) },
  ];

  return (
    <div>
      {err && <div className="blt-error">{err}</div>}
      <div className="card" style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
        <label className="blt-date-label">Khoảng thời gian:
          <select className="blt-date-input" style={{ marginLeft: 8 }} value={weeks}
                  onChange={(e) => setWeeks(Number(e.target.value))}>
            {WEEKS.map((w) => <option key={w} value={w}>{w} tuần gần nhất</option>)}
          </select>
        </label>
        <button className="btn btn-primary" onClick={onAdd}
                style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 6 }}>
          <PlusOutlined /> Thêm số liệu tuần
        </button>
      </div>

      <div className="card">
        <Table<Row>
          rowKey="key"
          size="small"
          bordered
          loading={loading}
          columns={columns}
          dataSource={rows}
          pagination={false}
          scroll={{ x: "max-content", y: 560 }}
          locale={{ emptyText: <Empty description="Chưa có số liệu tuần nào trong khoảng này." /> }}
        />
      </div>
    </div>
  );
}
