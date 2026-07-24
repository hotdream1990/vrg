import { AuditOutlined, FileExcelOutlined, ReloadOutlined } from "@ant-design/icons";
import { Select, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useState } from "react";

import {
  type AuditEntry,
  type AuditFilters,
  type AuditMeta,
  downloadAuditXlsx,
  fetchAuditLog,
  fetchAuditMeta,
} from "../../../lib/audit-client";
import { diffFields, summarize } from "../../../lib/audit-diff";
import { daysAgoISO, todayISO } from "../../../lib/date";
import { ROLE_COLOR, ROLE_LABEL } from "../../../lib/roles";
import AuditChangeDetail from "../sections/AuditChangeDetail";
import DateInput from "../sections/DateInput";
import "../../bulletin/bulletin.css";

const ACTION_COLOR: Record<string, string> = {
  create: "green", update: "blue", delete: "red", scan: "default",
};

const PAGE_SIZE = 50;
const EMPTY_META: AuditMeta = { entities: [], actions: [], actors: [], units: [] };

/** Thời điểm 'YYYY-MM-DDTHH:mm:ss...' → 'HH:mm:ss DD/MM/YYYY' (chuẩn VN). */
function stamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())} ${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`;
}

/** Tên người thao tác kèm ngữ cảnh: máy quét · link công khai · admin đăng nhập hộ. */
function actorCell(r: AuditEntry) {
  const isSystem = r.actor === "system";
  const isPublic = r.actor.startsWith("public:");
  return (
    <div style={{ lineHeight: 1.45 }}>
      <div style={{ fontWeight: 600 }}>
        {isSystem ? "Hệ thống (tự chạy)" : isPublic ? r.actor.slice("public:".length) : r.actor}
      </div>
      {isPublic && <div style={{ fontSize: 12, color: "#b45309" }}>Link công khai — không xác định người nhập</div>}
      {r.actor_role && <Tag color={ROLE_COLOR[r.actor_role]}>{ROLE_LABEL[r.actor_role] ?? r.actor_role}</Tag>}
      {r.on_behalf && <div style={{ fontSize: 12, color: "#b45309" }}>Do <b>{r.on_behalf}</b> đăng nhập hộ</div>}
      {r.ip && <div style={{ fontSize: 12, color: "var(--muted)" }}>IP {r.ip}</div>}
    </div>
  );
}

/** Quản trị → Nhật ký hoạt động: tra vết ai · lúc nào · sửa ô nào · từ giá trị nào sang giá trị nào. */
export default function AuditLogPage() {
  const [meta, setMeta] = useState<AuditMeta>(EMPTY_META);
  const [filters, setFilters] = useState<AuditFilters>({
    date_from: daysAgoISO(30), date_to: todayISO(),
  });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ items: AuditEntry[]; total: number }>({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => { fetchAuditMeta().then(setMeta).catch((e) => setErr(e.message)); }, []);

  const load = useCallback(() => {
    setLoading(true); setErr("");
    fetchAuditLog({ ...filters, page, page_size: PAGE_SIZE })
      .then((res) => setData({ items: res.items, total: res.total }))
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [filters, page]);
  useEffect(() => { load(); }, [load]);

  /** Đổi bộ lọc → luôn quay về trang 1 (kết quả cũ ở trang N không còn ý nghĩa). */
  const setFilter = (patch: Partial<AuditFilters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  };

  const columns: ColumnsType<AuditEntry> = [
    { title: "Thời điểm", dataIndex: "at", width: 150, render: stamp },
    { title: "Người thao tác", key: "actor", width: 185, render: (_, r) => actorCell(r) },
    {
      title: "Nhóm số liệu · Bản ghi", key: "entity", width: 290,
      render: (_, r) => (
        <div style={{ lineHeight: 1.45 }}>
          <div style={{ fontWeight: 600 }}>{r.entity_label}</div>
          <div style={{ fontSize: 12, color: "var(--muted)", wordBreak: "break-word" }}>
            {r.entity_key || "—"}{r.company ? ` · ${r.company}` : ""}
          </div>
          {r.note && <div style={{ fontSize: 12, color: "var(--muted)" }}>{r.note}</div>}
        </div>
      ),
    },
    {
      title: "Thao tác", dataIndex: "action", width: 105,
      render: (_, r) => <Tag color={ACTION_COLOR[r.action] ?? "default"}>{r.action_label}</Tag>,
    },
    {
      title: "Nội dung thay đổi", key: "diff",
      render: (_, r) => {
        const changes = diffFields(r.before, r.after);
        if (!changes.length) return <span style={{ color: "var(--muted)" }}>—</span>;
        return <span>{summarize(changes, r.action)}</span>;
      },
    },
  ];

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><AuditOutlined style={{ marginRight: 8 }} />Nhật ký hoạt động</h2>
          <p>Vết chỉnh sửa số liệu: <b>ai · lúc nào · sửa bản ghi nào · từ giá trị nào sang giá trị nào</b>.
            Mỗi lần ghi/xoá là một dòng riêng — bấm vào dòng để xem chi tiết trước/sau.</p>
          <p style={{ marginTop: 4 }}>Nhật ký chỉ đọc, không sửa/xoá được để bảo đảm giá trị đối chiếu.</p>
        </div>
      </div>
      {err && <div className="blt-error">{err}</div>}

      <div className="card" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <label className="blt-date-label">Từ ngày:
          <DateInput value={filters.date_from ?? ""} onChange={(v) => setFilter({ date_from: v })}
            style={{ marginLeft: 8 }} />
        </label>
        <label className="blt-date-label">Đến ngày:
          <DateInput value={filters.date_to ?? ""} onChange={(v) => setFilter({ date_to: v })}
            style={{ marginLeft: 8 }} />
        </label>
        <Select allowClear showSearch placeholder="Người thao tác" style={{ minWidth: 180 }}
          value={filters.actor} onChange={(v) => setFilter({ actor: v })}
          options={meta.actors.map((a) => ({ value: a, label: a }))} />
        <Select allowClear showSearch placeholder="Nhóm số liệu" style={{ minWidth: 220 }}
          value={filters.entity} onChange={(v) => setFilter({ entity: v })}
          options={meta.entities.map((e) => ({ value: e.key, label: e.label }))}
          filterOption={(i, o) => String(o?.label ?? "").toLowerCase().includes(i.toLowerCase())} />
        <Select allowClear placeholder="Thao tác" style={{ minWidth: 150 }}
          value={filters.action} onChange={(v) => setFilter({ action: v })}
          options={meta.actions.map((a) => ({ value: a.key, label: a.label }))} />
        <Select allowClear showSearch placeholder="Đơn vị" style={{ minWidth: 220 }}
          value={filters.company} onChange={(v) => setFilter({ company: v })}
          options={meta.units.map((u) => ({ value: u, label: u }))}
          filterOption={(i, o) => String(o?.label ?? "").toLowerCase().includes(i.toLowerCase())} />
        <input className="blt-date-input" placeholder="Tìm trong nội dung / bản ghi…"
          style={{ minWidth: 240 }} defaultValue={filters.q ?? ""}
          onKeyDown={(e) => { if (e.key === "Enter") setFilter({ q: e.currentTarget.value.trim() }); }}
          onBlur={(e) => setFilter({ q: e.currentTarget.value.trim() })} />
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button className="btn" onClick={load} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <ReloadOutlined /> Tải lại
          </button>
          <button className="btn btn-primary" disabled={exporting || !data.total}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            onClick={() => {
              setExporting(true); setErr("");
              downloadAuditXlsx(filters)
                .catch((e) => setErr(e instanceof Error ? e.message : "Lỗi xuất Excel"))
                .finally(() => setExporting(false));
            }}>
            {exporting ? <span className="spinner" /> : <FileExcelOutlined />} Xuất Excel
          </button>
        </div>
      </div>

      <div className="card">
        <Table<AuditEntry>
          rowKey="id" size="small" columns={columns} dataSource={data.items} loading={loading}
          scroll={{ x: 1000 }}   /* màn hẹp: cuộn ngang trong bảng, không vỡ trang */
          expandable={{ expandedRowRender: (r) => <AuditChangeDetail entry={r} /> }}
          pagination={{
            current: page, pageSize: PAGE_SIZE, total: data.total, showSizeChanger: false,
            onChange: setPage,
            showTotal: (t, [from, to]) => `${from}–${to} / ${t} thao tác`,
          }}
          locale={{ emptyText: "Không có thao tác nào khớp bộ lọc." }}
        />
      </div>
    </div>
  );
}
