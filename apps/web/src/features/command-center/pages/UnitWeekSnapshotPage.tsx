/* SNAPSHOT SỐ LIỆU TUẦN — bản lưu cố định thu mua · tiêu thụ · tồn kho của từng đơn vị, hệ thống
   tự chụp khi hết hạn nhập của ngày Chủ nhật. Trái: các tuần đã chụp · Phải: bảng của tuần đang chọn.
   Xem: quyền `unit_daily` (như Báo cáo tổng hợp). "Chụp ngay": chỉ quản trị, chỉ khi tuần gần nhất
   đã hết hạn nhập mà chưa có bản lưu (server không bao giờ chụp đè). */

import { CameraOutlined, DownloadOutlined, InfoCircleOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Empty, Popconfirm, Spin, Tag, message } from "antd";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import { dm, dmy } from "../../../lib/date";
import {
  type SnapshotDetail, type SnapshotStatus, type SnapshotSummary,
  downloadSnapshotXlsx, fetchSnapshot, fetchSnapshots, isLate, stampAt, takeSnapshotNow,
} from "../../../lib/unit-week-snapshot-client";
import UnitWeekSnapshotTable from "./UnitWeekSnapshotTable";
import "../../bulletin/bulletin.css";

/** Câu nói rõ bản lưu chụp lúc nào, do ai — người xem không nhầm với số đang sống. */
function takenLine(s: SnapshotSummary): string {
  const who = s.taken_by === "job" ? "chốt tự động" : `chụp theo lệnh của quản trị (${s.taken_by})`;
  return `Số liệu ${who} lúc ${stampAt(s.taken_at)} — sửa số liệu sau thời điểm này không làm đổi bản lưu.`;
}

export default function UnitWeekSnapshotPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState<SnapshotSummary[]>([]);
  const [status, setStatus] = useState<SnapshotStatus | null>(null);
  const [week, setWeek] = useState<string | null>(null);
  const [snap, setSnap] = useState<SnapshotDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const loadList = useCallback(() => {
    setLoading(true);
    fetchSnapshots()
      .then((r) => {
        setItems(r.items);
        setStatus(r.status);
        setWeek((w) => w ?? r.items[0]?.week_start ?? null);
      })
      .catch((e) => message.error(e.message))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { loadList(); }, [loadList]);

  useEffect(() => {
    if (!week) { setSnap(null); return; }
    let live = true;          // chỉ nhận lượt tải của tuần đang chọn (bấm nhanh không lẫn số tuần trước)
    setLoading(true);
    fetchSnapshot(week)
      .then((s) => { if (live) setSnap(s); })
      .catch((e) => message.error(e.message))
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [week]);

  const takeNow = async () => {
    setBusy(true);
    try {
      const r = await takeSnapshotNow();
      message.success(`Đã chụp số liệu ${r.week.label}.`);
      setWeek(r.week.week_start);
      loadList();
    } catch (e) { message.error((e as Error).message); } finally { setBusy(false); }
  };

  const exportXlsx = async () => {
    if (!snap) return;
    setBusy(true);
    try {
      await downloadSnapshotXlsx(snap);
      message.success("Đã tải file Excel.");
    } catch (e) { message.error((e as Error).message); } finally { setBusy(false); }
  };

  const due = status?.due;
  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><CameraOutlined style={{ marginRight: 8 }} />Snapshot số liệu tuần</h2>
          <p>
            Bản lưu cố định số liệu <b>thu mua · tiêu thụ · tồn kho</b> của từng đơn vị theo tuần (thứ Hai
            → Chủ nhật). Hệ thống tự chụp ngay khi <b>hết hạn nhập của ngày Chủ nhật</b>; số liệu cùng
            cách tính với màn Báo cáo tổng hợp. Tồn kho là số của <b>ngày cuối cùng có nhập tồn</b> trong
            tuần — xem cột Ngày lấy số tồn.
          </p>
        </div>
      </div>

      {status && (
        <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <InfoCircleOutlined style={{ color: "var(--info)" }} />
          <span>
            {status.next.label}: tự chụp sau hạn nhập <b>{stampAt(status.next.deadline_at)}</b>.
          </span>
          {due && !due.taken && (
            <span style={{ color: "var(--warn)" }}>
              {due.label} đã hết hạn nhập ({stampAt(due.deadline_at)}) nhưng chưa có bản lưu
              {isAdmin ? "." : " — hệ thống sẽ chụp ở lần chạy kế tiếp."}
            </span>
          )}
          <span style={{ flex: 1 }} />
          <Button icon={<ReloadOutlined />} onClick={loadList}>Làm mới</Button>
          {isAdmin && due && !due.taken && (
            <Popconfirm title={`Chụp ngay số liệu ${due.label}?`}
                        description="Bản lưu là cố định — đã chụp thì không chụp lại được."
                        okText="Chụp ngay" cancelText="Huỷ" onConfirm={takeNow}>
              <Button type="primary" icon={<CameraOutlined />} loading={busy}>Chụp ngay</Button>
            </Popconfirm>
          )}
        </div>
      )}

      <div style={{ display: "flex", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div className="card" style={{ flex: "0 0 260px", maxWidth: "100%", padding: 0 }}>
          <div style={{ padding: "10px 14px", fontWeight: 600, borderBottom: "1px solid var(--line)" }}>
            Các tuần đã chụp ({items.length})
          </div>
          {!items.length && !loading && (
            <Empty style={{ padding: 16 }} description="Chưa có bản lưu nào." />
          )}
          {items.map((it) => (
            <button key={it.week_start} type="button" onClick={() => setWeek(it.week_start)}
                    style={{
                      display: "block", width: "100%", textAlign: "left", border: 0, cursor: "pointer",
                      padding: "10px 14px", borderBottom: "1px solid var(--line)", color: "var(--text)",
                      background: it.week_start === week ? "rgba(125,125,125,.14)" : "transparent",
                    }}>
              <div style={{ fontWeight: 600 }}>
                Tuần {it.week_no}/{it.year}
                {it.taken_by !== "job" && <Tag style={{ marginLeft: 6 }}>chụp tay</Tag>}
                {isLate(it) && <Tag color="orange" style={{ marginLeft: 6 }}>chụp sau hạn</Tag>}
              </div>
              <div style={{ fontSize: 12.5, color: "var(--muted)" }}>{dm(it.week_start)} – {dmy(it.week_end)}</div>
              <div style={{ fontSize: 12, color: "var(--muted)" }}>Chụp {stampAt(it.taken_at)}</div>
            </button>
          ))}
        </div>

        <div style={{ flex: "1 1 560px", minWidth: 0 }}>
          <Spin spinning={loading}>
            {snap ? (
              <>
                <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                  <b style={{ fontSize: 15 }}>{snap.label}</b>
                  <span style={{ flex: 1 }} />
                  <Button type="primary" icon={<DownloadOutlined />} onClick={exportXlsx} loading={busy}>
                    Xuất Excel
                  </Button>
                </div>
                <Alert type={isLate(snap) ? "warning" : "info"} showIcon style={{ marginBottom: 12 }}
                       message={takenLine(snap)}
                       description={`Hạn nhập số liệu ngày Chủ nhật: ${stampAt(snap.deadline_at)}.`
                         + (isLate(snap) ? " Bản này chụp sau hạn — số có thể gồm cả phần sửa sau hạn." : "")} />
                <UnitWeekSnapshotTable snap={snap} />
              </>
            ) : (
              !loading && <div className="card"><Empty description="Chọn một tuần đã chụp ở cột bên trái." /></div>
            )}
          </Spin>
        </div>
      </div>
    </div>
  );
}
