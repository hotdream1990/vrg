/* Danh sách BÁO CÁO dạng BẢNG theo dòng thời gian (ẩn ngày trống) — DÙNG CHUNG cho đơn vị
   thành viên (đơn vị được gán) và chuyên viên (mọi đơn vị). Mỗi dòng = 1 (ngày × đơn vị); cột số
   liệu giữ đúng thứ tự Excel; ô "Ngày" gộp cho các đơn vị cùng ngày. */

import { EditOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Empty, Table, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";

import { dmy } from "../../../lib/date";
import { dataColumns } from "../../../lib/unit-daily-columns";
import {
  type Timeline, type TimelineRow, fetchMyDailyTimeline, fetchDailyTimeline,
} from "../../../lib/unit-daily-client";
import type { Kind } from "../../../lib/unit-daily-fields";

const DAY_RANGES = [30, 60, 90, 180];

type Row = TimelineRow & { key: string; _daySpan: number };

type Props = {
  kind: Kind;
  role: "member" | "hq";
  isAdmin: boolean;
  refreshKey: number;
  onEdit: (asOf: string, company: string) => void;
  onAdd: () => void;
};

export default function UnitDailyTimeline({ kind, role, refreshKey, onEdit, onAdd }: Props) {
  const [days, setDays] = useState(90);
  const [data, setData] = useState<Timeline | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setLoading(true); setErr("");
    (role === "member" ? fetchMyDailyTimeline : fetchDailyTimeline)(kind, days)
      .then(setData).catch((e) => setErr(e.message)).finally(() => setLoading(false));
  }, [role, kind, days]);
  useEffect(() => { load(); }, [load, refreshKey]);

  // Rows theo thứ tự backend (ngày DESC, đơn vị); tính rowSpan gộp ô "Ngày".
  const rows = useMemo<Row[]>(() => {
    const es = data?.entries ?? [];
    const counts: Record<string, number> = {};
    es.forEach((e) => { counts[e.as_of] = (counts[e.as_of] ?? 0) + 1; });
    const seen = new Set<string>();
    return es.map((e) => {
      const span = seen.has(e.as_of) ? 0 : counts[e.as_of];
      seen.add(e.as_of);
      return { ...e, key: `${e.as_of}|${e.company}`, _daySpan: span };
    });
  }, [data]);

  const columns: ColumnsType<Row> = [
    { title: "Ngày", key: "day", fixed: "left", width: 130,
      onCell: (r) => ({ rowSpan: r._daySpan }),
      render: (_: unknown, r: Row) => <b style={{ color: "#0a9e48" }}>{dmy(r.as_of)}</b> },
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
        <Button size="small" type="link" icon={<EditOutlined />} onClick={() => onEdit(r.as_of, r.company)} />
      ) },
  ];

  return (
    <div>
      {err && <div className="blt-error">{err}</div>}
      <div className="card" style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
        <label className="blt-date-label">Khoảng thời gian:
          <select className="blt-date-input" style={{ marginLeft: 8 }} value={days}
                  onChange={(e) => setDays(Number(e.target.value))}>
            {DAY_RANGES.map((d) => <option key={d} value={d}>{d} ngày gần nhất</option>)}
          </select>
        </label>
        <button className="btn btn-primary" onClick={onAdd}
                style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 6 }}>
          <PlusOutlined /> Thêm số liệu ngày
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
          locale={{ emptyText: <Empty description="Chưa có số liệu ngày nào trong khoảng này." /> }}
        />
      </div>
    </div>
  );
}
