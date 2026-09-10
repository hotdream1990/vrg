/* Lịch sử hỏi đáp — Trợ lý AI: xem lại các phiên hội thoại cũ (đầy đủ lượt hỏi–đáp, công cụ đã
   gọi, nguồn dữ liệu) và dọn bớt log cho nhẹ. Gác cap `assistant`; xoá + lọc theo người dùng
   chỉ dành cho admin (backend chặn lần nữa). Bảng PHÂN TRANG Ở SERVER — không tải hết dữ liệu. */

import {
  DatabaseOutlined, DeleteOutlined, HistoryOutlined, ReloadOutlined, ToolOutlined,
} from "@ant-design/icons";
import {
  Alert, App, Button, DatePicker, Drawer, Empty, Input, Modal, Popconfirm, Select, Spin, Table, Tag,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import type { Dayjs } from "dayjs";
import { useCallback, useEffect, useState } from "react";

import {
  type HistorySession, type HistoryStats, type HistoryTurn,
  deleteSession, fetchHistoryStats, fetchSessionTurns, fetchSessions, purgeHistoryBefore,
} from "../../../lib/assistant-history-client";
import { daysAgoISO, dmy } from "../../../lib/date";
import { listUsers } from "../../../lib/user-client";
import { useAuth } from "../../auth/AuthContext";
import DateInput from "../sections/DateInput";

const { RangePicker } = DatePicker;

const PAGE_SIZE = 20;
const DATE_DISPLAY = "DD/MM/YYYY";
const ISO_DATE = "YYYY-MM-DD";
const PURGE_DEFAULT_DAYS = 90;      // mốc gợi ý sẵn ở hộp dọn log: giữ 3 tháng gần nhất
const MS_PER_SECOND = 1000;

type RangeValue = [Dayjs | null, Dayjs | null] | null;

/** Mức tư vấn của lượt hỏi (giới hạn Trợ lý được đi xa tới đâu) → nhãn tiếng Việt + màu thẻ.
 *  Phải khớp `ADVICE_MODES` ở `apps/api/app/services/assistant_service.py`. */
const ADVICE_LABEL: Record<string, { text: string; color: string }> = {
  data: { text: "Chỉ tra số", color: "blue" },
  model: { text: "Theo mô hình", color: "green" },
  adjusted: { text: "Có điều chỉnh", color: "orange" },
};
const adviceTag = (advice: string) =>
  ADVICE_LABEL[advice.toLowerCase()] ?? { text: advice, color: "purple" };

const errText = (e: unknown): string => (e instanceof Error ? e.message : "Có lỗi xảy ra, vui lòng thử lại.");

/** Thời điểm ISO → 'HH:mm DD/MM/YYYY' (chuẩn VN). */
function stamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())} ${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`;
}

/** Hàng thẻ có nhãn (công cụ · nguồn · gói kỹ năng) — rỗng thì không chiếm chỗ. */
function TagRow({ label, items, icon }: { label: string; items: string[]; icon?: JSX.Element }) {
  if (items.length === 0) return null;
  return (
    <div style={{ marginTop: 6, fontSize: 12.5 }}>
      <span style={{ color: "var(--muted)", marginRight: 6 }}>{icon} {label}:</span>
      {items.map((it) => <Tag key={it} style={{ marginBottom: 4 }}>{it}</Tag>)}
    </div>
  );
}

/** Một lượt hỏi–đáp trong ngăn chi tiết. */
function TurnCard({ turn, index }: { turn: HistoryTurn; index: number }) {
  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <b>Lượt {index + 1}</b>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>{stamp(turn.created_at)}</span>
        {turn.advice && (
          <Tag color={adviceTag(turn.advice).color}>Mức tư vấn: {adviceTag(turn.advice).text}</Tag>
        )}
        {turn.model && <Tag>{turn.model}</Tag>}
        {turn.latency_ms > 0 && (
          <span style={{ color: "var(--muted)", fontSize: 12 }}>
            {(turn.latency_ms / MS_PER_SECOND).toFixed(1)} giây
          </span>
        )}
      </div>
      <div style={{ fontWeight: 600, marginBottom: 6, whiteSpace: "pre-wrap" }}>{turn.question}</div>
      <div style={{ whiteSpace: "pre-wrap" }}>{turn.answer}</div>
      <TagRow label="Công cụ đã gọi" items={turn.tools} icon={<ToolOutlined />} />
      <TagRow label="Nguồn dữ liệu" items={turn.sources} icon={<DatabaseOutlined />} />
      <TagRow label="Gói kỹ năng" items={turn.packs ?? []} />
    </div>
  );
}

export default function AssistantHistoryPage() {
  const { user } = useAuth();
  const { message } = App.useApp();
  const isAdmin = user?.role === "admin";

  const [range, setRange] = useState<RangeValue>(null);
  const [q, setQ] = useState("");
  const [username, setUsername] = useState<string | undefined>(undefined);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ items: HistorySession[]; total: number }>({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [userOptions, setUserOptions] = useState<string[]>([]);
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [active, setActive] = useState<HistorySession | null>(null);
  const [turns, setTurns] = useState<HistoryTurn[]>([]);
  const [turnsLoading, setTurnsLoading] = useState(false);
  const [purgeOpen, setPurgeOpen] = useState(false);
  const [purgeDate, setPurgeDate] = useState(daysAgoISO(PURGE_DEFAULT_DAYS));
  const [purging, setPurging] = useState(false);

  const load = useCallback(() => {
    setLoading(true); setErr("");
    fetchSessions({
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
      username: isAdmin ? username : undefined,
      date_from: range?.[0]?.format(ISO_DATE),
      date_to: range?.[1]?.format(ISO_DATE),
      q: q || undefined,
    })
      .then((res) => setData({ items: res.items, total: res.total }))
      .catch((e) => setErr(errText(e)))
      .finally(() => setLoading(false));
  }, [page, isAdmin, username, range, q]);
  useEffect(() => { load(); }, [load]);

  const loadStats = useCallback(() => {
    if (!isAdmin) return;
    fetchHistoryStats().then(setStats).catch(() => setStats(null));
  }, [isAdmin]);
  useEffect(() => { loadStats(); }, [loadStats]);

  // Danh sách người dùng cho ô lọc — chỉ admin mới gọi được endpoint này.
  useEffect(() => {
    if (!isAdmin) return;
    listUsers().then((us) => setUserOptions(us.map((u) => u.username))).catch(() => setUserOptions([]));
  }, [isAdmin]);

  /** Đổi bộ lọc → luôn về trang 1 (kết quả cũ ở trang N không còn ý nghĩa). */
  const resetToFirstPage = () => setPage(1);

  /** Sau khi xoá nhiều dòng: về trang 1; đang ở trang 1 thì tự nạp lại (đổi `page` mới nạp lại). */
  const reloadFromStart = () => { if (page === 1) load(); else setPage(1); };

  const openSession = (row: HistorySession) => {
    setActive(row); setTurns([]); setTurnsLoading(true);
    fetchSessionTurns(row.session_id)
      // Sắp cũ → mới ngay tại đây: đọc lại hội thoại phải theo đúng thứ tự đã diễn ra.
      .then((items) => setTurns([...items].sort((a, b) => a.created_at.localeCompare(b.created_at))))
      .catch((e) => message.error(errText(e)))
      .finally(() => setTurnsLoading(false));
  };

  const removeSession = async (sessionId: string) => {
    try {
      const deleted = await deleteSession(sessionId);
      message.success(deleted === null
        ? "Đã xoá phiên hỏi đáp."
        : `Đã xoá phiên hỏi đáp (${deleted} lượt).`);
      if (active?.session_id === sessionId) setActive(null);
      load(); loadStats();
    } catch (e) {
      message.error(errText(e));
    }
  };

  const runPurge = async () => {
    if (!purgeDate) return;
    setPurging(true);
    try {
      const deleted = await purgeHistoryBefore(purgeDate);
      message.success(`Đã xoá ${deleted} lượt hỏi đáp trước ngày ${dmy(purgeDate)}.`);
      setPurgeOpen(false); setActive(null);
      reloadFromStart(); loadStats();
    } catch (e) {
      message.error(errText(e));
    } finally {
      setPurging(false);
    }
  };

  const userColumn: ColumnsType<HistorySession> = isAdmin
    ? [{ title: "Người hỏi", dataIndex: "username", width: 170, ellipsis: true }]
    : [];
  const actionColumn: ColumnsType<HistorySession> = isAdmin
    ? [{
      title: "", key: "action", width: 60, align: "center",
      render: (_, r) => (
        // Bọc để cú bấm xoá không lọt xuống dòng (bấm dòng = mở chi tiết).
        <span onClick={(e) => e.stopPropagation()}>
          <Popconfirm
            title="Xoá phiên hỏi đáp này?"
            description="Toàn bộ lượt hỏi–đáp trong phiên sẽ bị xoá vĩnh viễn."
            okText="Xoá" cancelText="Huỷ" okButtonProps={{ danger: true }}
            onConfirm={() => removeSession(r.session_id)}
          >
            <Button type="text" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </span>
      ),
    }]
    : [];

  const columns: ColumnsType<HistorySession> = [
    {
      title: "Thời gian", key: "time", width: 200,
      render: (_, r) => (
        <div style={{ lineHeight: 1.45 }}>
          <div style={{ fontWeight: 600 }}>{stamp(r.first_at)}</div>
          <div style={{ fontSize: 12, color: "var(--muted)" }}>Lượt cuối: {stamp(r.last_at)}</div>
        </div>
      ),
    },
    ...userColumn,
    { title: "Số lượt", dataIndex: "turns", width: 90, align: "center" },
    {
      title: "Tiêu đề (câu hỏi đầu)", dataIndex: "title",
      render: (v: string) => v || <span style={{ color: "var(--muted)" }}>—</span>,
    },
    ...actionColumn,
  ];

  const statsText = stats
    ? `Đang lưu ${stats.turns} lượt trong ${stats.sessions} phiên, cũ nhất từ ${dmy(stats.oldest)}.`
    : "Đang đọc thống kê log…";

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><HistoryOutlined style={{ marginRight: 8 }} />Lịch sử hỏi đáp — Trợ lý AI</h2>
          <p>Xem lại các phiên hội thoại với Trợ lý AI: câu hỏi, câu trả lời, công cụ đã gọi và nguồn
            số liệu. Bấm vào một dòng để mở toàn bộ lượt hỏi–đáp của phiên đó.</p>
        </div>
      </div>
      {err && <Alert type="error" showIcon message={err} style={{ marginBottom: 12 }} />}

      <div className="card" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <RangePicker
          format={DATE_DISPLAY} allowEmpty={[true, true]} value={range}
          placeholder={["Từ ngày", "Đến ngày"]}
          onChange={(v) => { setRange(v); resetToFirstPage(); }}
        />
        <Input.Search
          allowClear placeholder="Tìm theo câu hỏi…" style={{ maxWidth: 320 }}
          onSearch={(v) => { setQ(v.trim()); resetToFirstPage(); }}
          // Xoá trắng ô = bỏ lọc ngay: antd chỉ gọi onSearch khi Enter/bấm nút, không gọi khi bấm dấu xoá.
          onChange={(e) => { if (!e.target.value) { setQ(""); resetToFirstPage(); } }}
        />
        {isAdmin && (
          <Select
            allowClear showSearch placeholder="Người hỏi" style={{ minWidth: 200 }}
            value={username} onChange={(v) => { setUsername(v); resetToFirstPage(); }}
            options={userOptions.map((u) => ({ value: u, label: u }))}
          />
        )}
        <Button icon={<ReloadOutlined />} style={{ marginLeft: "auto" }} onClick={load}>Tải lại</Button>
      </div>

      {isAdmin && (
        <div className="card" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginTop: 12 }}>
          <DatabaseOutlined />
          <span>{statsText}</span>
          <Button danger icon={<DeleteOutlined />} style={{ marginLeft: "auto" }} onClick={() => setPurgeOpen(true)}>
            Xoá log cũ hơn…
          </Button>
        </div>
      )}

      <div className="card" style={{ marginTop: 12 }}>
        <Table<HistorySession>
          rowKey="session_id" size="small" columns={columns} dataSource={data.items} loading={loading}
          scroll={{ x: 800 }}
          onRow={(r) => ({ onClick: () => openSession(r), style: { cursor: "pointer" } })}
          pagination={{
            current: page, pageSize: PAGE_SIZE, total: data.total, showSizeChanger: false,
            onChange: setPage,
            showTotal: (t, [from, to]) => `${from}–${to} / ${t} phiên`,
          }}
          locale={{ emptyText: "Chưa có phiên hỏi đáp nào khớp bộ lọc." }}
        />
      </div>

      <Drawer
        open={Boolean(active)} width={760} onClose={() => setActive(null)}
        title={active ? `Phiên ngày ${stamp(active.first_at)} · ${active.turns} lượt` : ""}
        extra={active && isAdmin ? (
          <Popconfirm
            title="Xoá phiên hỏi đáp này?" description="Toàn bộ lượt hỏi–đáp trong phiên sẽ bị xoá vĩnh viễn."
            okText="Xoá" cancelText="Huỷ" okButtonProps={{ danger: true }}
            onConfirm={() => removeSession(active.session_id)}
          >
            <Button danger size="small" icon={<DeleteOutlined />}>Xoá phiên</Button>
          </Popconfirm>
        ) : undefined}
      >
        {isAdmin && active && (
          <p style={{ color: "var(--muted)", marginTop: 0 }}>Người hỏi: <b>{active.username}</b></p>
        )}
        {turnsLoading
          ? <div style={{ textAlign: "center", padding: 32 }}><Spin /></div>
          : turns.length === 0
            ? <Empty description="Không đọc được lượt hỏi đáp nào của phiên này." />
            : turns.map((t, i) => <TurnCard key={t.id} turn={t} index={i} />)}
      </Drawer>

      <Modal
        open={purgeOpen} title="Xoá log hỏi đáp cũ" onCancel={() => setPurgeOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setPurgeOpen(false)}>Huỷ</Button>,
          <Popconfirm
            key="purge" title={`Xoá toàn bộ lượt hỏi đáp trước ngày ${dmy(purgeDate)}?`}
            description="Log đã xoá không khôi phục được." okText="Xoá" cancelText="Huỷ"
            okButtonProps={{ danger: true }} onConfirm={runPurge}
          >
            <Button type="primary" danger loading={purging} disabled={!purgeDate}>Xoá log cũ</Button>
          </Popconfirm>,
        ]}
      >
        <p>Xoá mọi lượt hỏi đáp có thời điểm <b>trước</b> ngày chọn; log từ ngày đó trở đi được giữ lại.</p>
        <DateInput value={purgeDate} onChange={setPurgeDate} noFuture />
        <p className="form-note" style={{ marginTop: 10 }}>
          Lưu ý: thao tác xoá vĩnh viễn, không hoàn tác được.
        </p>
      </Modal>
    </div>
  );
}
