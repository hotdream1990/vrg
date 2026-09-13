import { ClockCircleOutlined } from "@ant-design/icons";
import { App, Button, Space, Switch, Table, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";

import { type ScheduleJob, fetchSchedules, runSchedule, updateSchedule } from "../../../lib/api-client";
import "../../bulletin/bulletin.css";

const STATUS: Record<string, { label: string; color: string }> = {
  ok: { label: "Thành công", color: "green" },
  // Chạy xong nhưng có nguồn lỗi / tỷ giá quá cũ — lý do hiện ngay dưới (meta_crawl_run.error).
  warning: { label: "Có cảnh báo", color: "gold" },
  error: { label: "Lỗi", color: "red" },
  empty: { label: "Không có dữ liệu", color: "default" },
  running: { label: "Đang chạy", color: "blue" },
};

const hhmm = (h: number, m: number) => `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;

/** Chu kỳ hiển thị dưới ô giờ — job theo tuần chỉ chạy đúng thứ của nó. */
const DOW: Record<string, string> = {
  mon: "Thứ Hai", tue: "Thứ Ba", wed: "Thứ Tư", thu: "Thứ Năm",
  fri: "Thứ Sáu", sat: "Thứ Bảy", sun: "Chủ nhật",
};
const cycle = (dow: string | null) => (dow ? `${DOW[dow] ?? dow} hằng tuần` : "Hằng ngày");
const dt = (s: string) => new Date(s).toLocaleString("vi-VN");

type EditState = Record<string, { time: string; enabled: boolean }>;

/** Quản trị → Lịch chạy (chỉ admin). Tác vụ tự động do scheduler trong app chạy theo giờ. */
export default function SchedulePage() {
  const { message } = App.useApp();
  const [jobs, setJobs] = useState<ScheduleJob[]>([]);
  const [edit, setEdit] = useState<EditState>({});
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    const r = await fetchSchedules();
    setJobs(r.jobs);
    setEdit(Object.fromEntries(r.jobs.map((j) => [j.name, { time: hhmm(j.hour, j.minute), enabled: j.enabled }])));
  }, []);

  useEffect(() => { load(); }, [load]);

  const patch = (name: string, p: Partial<{ time: string; enabled: boolean }>) =>
    setEdit((s) => ({ ...s, [name]: { ...s[name], ...p } }));

  const save = async (name: string) => {
    const e = edit[name];
    const [h, m] = e.time.split(":").map(Number);
    await updateSchedule(name, { hour: h, minute: m, enabled: e.enabled });
    message.success("Đã lưu lịch.");
    load();
  };

  const runNow = async (name: string) => {
    setBusy(name);
    try {
      const r = await runSchedule(name);
      const err = r.sources?.find((s) => s.status === "error");
      if (err) message.error(err.note || "Chạy thất bại");
      else if (r.warnings?.length) message.warning(`Đã ghi ${r.persisted} bản ghi — cảnh báo: ${r.warnings.join(" · ")}`);
      // Job không phải quét giá tự mô tả kết quả trong `note` (vd chốt tồn kho: mấy tuần được ghi).
      else message.success(r.sources?.[0]?.note || `Đã ghi ${r.persisted} bản ghi`);
      load();
    } catch (e) {
      message.error(String(e));
    } finally {
      setBusy(null);
    }
  };

  const columns = [
    {
      title: "Tác vụ", key: "label",
      render: (_: unknown, j: ScheduleJob) => (
        <div><b>{j.label}</b><div style={{ fontSize: 11, color: "var(--muted)" }}>{j.purpose}</div></div>
      ),
    },
    {
      title: "Giờ chạy", key: "time",
      render: (_: unknown, j: ScheduleJob) => (
        <div>
          <input type="time" className="blt-date-input"
            value={edit[j.name]?.time ?? ""}
            onChange={(e) => patch(j.name, { time: e.target.value })} />
          <div style={{ fontSize: 11, color: "var(--muted)" }}>{cycle(j.day_of_week)}</div>
        </div>
      ),
    },
    {
      title: "Bật", key: "enabled",
      render: (_: unknown, j: ScheduleJob) => (
        <Switch checked={edit[j.name]?.enabled ?? false} onChange={(v) => patch(j.name, { enabled: v })} />
      ),
    },
    {
      title: "Lần chạy gần nhất", key: "last",
      render: (_: unknown, j: ScheduleJob) => j.last_run ? (
        <div>
          <Space size={6}>
            <Tag color={STATUS[j.last_run.status]?.color}>{STATUS[j.last_run.status]?.label ?? j.last_run.status}</Tag>
            <span style={{ fontSize: 12 }}>{dt(j.last_run.started_at)}</span>
          </Space>
          {j.last_run.status !== "ok" && j.last_run.error && (
            <div style={{ fontSize: 11, color: "#a96a00", maxWidth: 360 }} title={j.last_run.error}>
              {j.last_run.error.length > 140 ? `${j.last_run.error.slice(0, 140)}…` : j.last_run.error}
            </div>
          )}
        </div>
      ) : <span style={{ color: "var(--muted)" }}>Chưa chạy</span>,
    },
    {
      title: "Kế tiếp", key: "next",
      render: (_: unknown, j: ScheduleJob) =>
        edit[j.name]?.enabled && j.next_run ? <span style={{ fontSize: 12 }}>{dt(j.next_run)}</span> : "—",
    },
    {
      title: "", key: "act",
      render: (_: unknown, j: ScheduleJob) => (
        <Space>
          <Button size="small" onClick={() => save(j.name)}>Lưu</Button>
          <Button size="small" type="primary" loading={busy === j.name} onClick={() => runNow(j.name)}>
            Chạy ngay
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ClockCircleOutlined style={{ marginRight: 8 }} />Lịch chạy</h2>
          <p>Tác vụ tự động chạy theo giờ — do hệ thống tự lên lịch (không cài đặt vào máy chủ).
            Sửa giờ, bật/tắt hoặc bấm "Chạy ngay". Job lỡ giờ vì máy chủ tắt/khởi động lại sẽ được
            <b> chạy bù ngay sau khi hệ thống lên lại</b>.</p>
        </div>
      </div>
      <div className="card">
        <Table rowKey="name" dataSource={jobs} columns={columns} pagination={false} />
      </div>
    </div>
  );
}
