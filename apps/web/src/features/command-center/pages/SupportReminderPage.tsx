import {
  ArrowLeftOutlined, DeleteOutlined, EditOutlined, PlusOutlined, ScheduleOutlined, ThunderboltOutlined,
} from "@ant-design/icons";
import { Modal, Switch, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  type Reminder, type SupportContext,
  deleteReminder, fetchReminders, fetchSupportContext, runReminder, updateReminder,
} from "../../../lib/support-client";
import ReminderFormModal from "../sections/ReminderFormModal";
import { AudienceTags } from "../sections/SupportAudience";
import { REPEAT_LABEL, SCOPE_LABEL, audienceOf, stampVN } from "../sections/support-format";
import "../../bulletin/bulletin.css";
import "../support.css";

/** Nhắc lịch — Tập đoàn hẹn giờ, tới hạn hệ thống tự gửi thông báo + email cho các đơn vị đã chọn.
 *
 *  Tin nhắc đi đúng đường thông báo thường: mỗi đơn vị một luồng riêng, đơn vị phản hồi ngay
 *  trong luồng đó. */
export default function SupportReminderPage() {
  const nav = useNavigate();
  const [ctx, setCtx] = useState<SupportContext | null>(null);
  const [rows, setRows] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState<Reminder | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => { fetchSupportContext().then(setCtx).catch((e) => setErr(e.message)); }, []);

  const load = useCallback(() => {
    setLoading(true); setErr("");
    fetchReminders().then((r) => setRows(r.rows))
      .catch((e) => setErr(e.message)).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const toggle = async (r: Reminder, enabled: boolean) => {
    try {
      await updateReminder(r.id, { ...r, audience: audienceOf(r.audience), enabled });
      load();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  const runNow = (r: Reminder) => {
    Modal.confirm({
      title: "Gửi ngay lịch nhắc này?",
      content: `Gửi tới ${r.target_count ?? 0} đơn vị ngay bây giờ. Mốc nhắc định kỳ giữ nguyên.`,
      okText: "Gửi ngay", cancelText: "Huỷ",
      onOk: async () => {
        const res = await runReminder(r.id);
        message.success(`Đã gửi tới ${res.threads} đơn vị.`);
        load();
      },
    });
  };

  const remove = (r: Reminder) => {
    Modal.confirm({
      title: "Xoá lịch nhắc?",
      content: `Xoá "${r.title}". Các tin đã gửi trước đó vẫn giữ nguyên.`,
      okText: "Xoá", okButtonProps: { danger: true }, cancelText: "Huỷ",
      onOk: async () => { await deleteReminder(r.id); load(); },
    });
  };

  const columns: ColumnsType<Reminder> = [
    {
      title: "Nội dung nhắc", dataIndex: "title",
      render: (v: string, r) => (
        <div>
          <div style={{ fontWeight: 600 }}>{v}</div>
          {r.body && <div style={{ color: "var(--muted)", fontSize: 12.5 }}>{r.body.slice(0, 120)}</div>}
        </div>
      ),
    },
    {
      title: "Gửi tới", dataIndex: "scope",
      render: (v: string, r) => (
        <div>
          <Tag>{SCOPE_LABEL[v] ?? v}</Tag>
          {v === "region" && r.region && <div style={{ fontSize: 12 }}>{r.region}</div>}
          <div style={{ color: "var(--muted)", fontSize: 12 }}>{r.target_count ?? 0} đơn vị</div>
          <div style={{ marginTop: 4 }}><AudienceTags audience={r.audience} /></div>
        </div>
      ),
    },
    { title: "Chu kỳ", dataIndex: "repeat_rule", render: (v: string) => REPEAT_LABEL[v] ?? v },
    { title: "Lần nhắc kế tiếp", dataIndex: "next_at", render: (v: string) => stampVN(v) },
    { title: "Đã gửi lần cuối", dataIndex: "last_sent_at", render: (v: string | null) => stampVN(v) },
    {
      title: "Bật", dataIndex: "enabled", width: 80,
      render: (v: boolean, r) => <Switch checked={v} onChange={(c) => toggle(r, c)} />,
    },
    {
      title: "", width: 190,
      render: (_: unknown, r) => (
        <div style={{ display: "flex", gap: 6 }}>
          <button className="btn" onClick={() => setEditing(r)}><EditOutlined /></button>
          <button className="btn" onClick={() => runNow(r)}><ThunderboltOutlined /> Gửi ngay</button>
          <button className="btn" onClick={() => remove(r)}><DeleteOutlined /></button>
        </div>
      ),
    },
  ];

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ScheduleOutlined style={{ marginRight: 8 }} />Nhắc lịch</h2>
          <p>Hẹn giờ nhắc việc cho đơn vị thành viên. Tới hạn, hệ thống tự gửi thông báo vào hộp thư
            của từng đơn vị kèm email — đơn vị phản hồi ngay trong tin đó.</p>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => nav("/ho-tro")}><ArrowLeftOutlined /> Hộp thư</button>
          <button className="btn btn-primary" onClick={() => setCreating(true)}>
            <PlusOutlined /> Tạo lịch nhắc
          </button>
        </div>
      </div>

      {err && <div className="blt-error">{err}</div>}

      <div className="card">
        <Table rowKey="id" size="small" loading={loading} columns={columns} dataSource={rows}
          pagination={false} locale={{ emptyText: "Chưa có lịch nhắc nào." }} />
      </div>

      {(creating || editing) && ctx && (
        <ReminderFormModal ctx={ctx} reminder={editing}
          onClose={() => { setCreating(false); setEditing(null); }}
          onSaved={() => { setCreating(false); setEditing(null); load(); }} />
      )}
    </div>
  );
}
