import {
  CheckCircleFilled, DeleteOutlined, LockOutlined, PlusOutlined, ReloadOutlined,
  UnlockOutlined, WarningFilled,
} from "@ant-design/icons";
import { Modal } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  type LockRound, type LockStatus, cancelLockRound, deleteLockRound, fetchLockRounds,
  fetchLockStatus, lockUnits, saveLockRound, unlockUnits,
} from "../../../lib/data-lock-client";
import { useAuth } from "../../auth/AuthContext";
import DateInput from "../sections/DateInput";
import DataLockConfirmModal from "../sections/DataLockConfirmModal";

const dmy = (iso?: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");
const stamp = (iso?: string | null) =>
  (iso ? new Date(iso).toLocaleString("vi-VN", { hour12: false }) : "—");
const n3 = (v: unknown) =>
  (typeof v === "number" && Number.isFinite(v) ? v.toLocaleString("vi-VN", { maximumFractionDigits: 3 }) : "—");

/** Form tạo/sửa một đợt chốt (chỉ quản trị). */
function RoundForm({ initial, onClose, onSaved }: {
  initial?: LockRound | null; onClose: () => void; onSaved: () => void;
}) {
  const [lockDate, setLockDate] = useState(initial?.lock_date ?? "");
  const [note, setNote] = useState(initial?.note ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!lockDate) { setErr("Chọn ngày chốt số liệu."); return; }
    setBusy(true); setErr("");
    try {
      await saveLockRound({ id: initial?.id, lock_date: lockDate, note: note.trim() || null });
      onSaved(); onClose();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  return (
    <Modal open width="min(620px, 94vw)" destroyOnHidden
      title={initial ? `Sửa đợt chốt ${dmy(initial.lock_date)}` : "Yêu cầu chốt số liệu"}
      onCancel={onClose} onOk={submit} okText="Lưu" cancelText="Đóng"
      okButtonProps={{ loading: busy }}>
      <label className="form-field" style={{ display: "block" }}>Chốt số liệu đến hết ngày *
        <DateInput value={lockDate} onChange={setLockDate} />
      </label>
      <label className="form-field" style={{ display: "block", marginTop: 10 }}>
        Lời nhắn cho đơn vị
        <textarea className="blt-date-input" rows={2} style={{ width: "100%", resize: "vertical" }}
          value={note} placeholder="vd: Chốt số liệu tháng 8 để tổng hợp báo cáo Tập đoàn"
          onChange={(e) => setNote(e.target.value)} />
      </label>
      <div className="form-note" style={{ marginTop: 10, fontSize: 12 }}>
        Mọi đơn vị thành viên sẽ thấy cảnh báo trên đầu màn hình kèm bảng số liệu đến ngày này.
        Đơn vị xác nhận xong là <b>hết tự sửa</b> số liệu thu mua · tiêu thụ · tồn kho của những
        ngày đó; chuyên viên và quản trị vẫn sửa được.
      </div>
      {err && <div className="blt-error" style={{ marginTop: 8 }}>{err}</div>}
    </Modal>
  );
}

/**
 * Quản trị → **Chốt số liệu**: phát đợt chốt và theo dõi đơn vị nào đã/chưa xác nhận.
 *
 * Một trang gộp hai việc vì chúng luôn đi cùng nhau: phát yêu cầu xong là phải nhìn được ai chưa
 * làm để đốc thúc. Bảng lọc sẵn "chưa xác nhận" — đúng việc Ban TTKD cần làm hằng ngày.
 */
export default function DataLockPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [rounds, setRounds] = useState<LockRound[]>([]);
  const [roundId, setRoundId] = useState<number | null>(null);
  const [status, setStatus] = useState<LockStatus | null>(null);
  const [onlyPending, setOnlyPending] = useState(false);
  const [q, setQ] = useState("");
  const [form, setForm] = useState<{ initial: LockRound | null } | null>(null);
  const [view, setView] = useState<{ company: string; roundId: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const loadRounds = useCallback(() => {
    fetchLockRounds().then((r) => {
      setRounds(r.items);
      setRoundId((cur) => cur ?? r.items.find((x) => !x.cancelled_at)?.id ?? r.items[0]?.id ?? null);
    }).catch((e) => setErr(e instanceof Error ? e.message : "Lỗi"));
  }, []);

  const loadStatus = useCallback(() => {
    fetchLockStatus({ round_id: roundId ?? undefined, only_pending: onlyPending, q: q || undefined })
      .then(setStatus).catch((e) => setErr(e instanceof Error ? e.message : "Lỗi"));
  }, [roundId, onlyPending, q]);

  useEffect(() => { loadRounds(); }, [loadRounds]);
  useEffect(() => { loadStatus(); }, [loadStatus]);

  const round = useMemo(() => rounds.find((r) => r.id === roundId) ?? null, [rounds, roundId]);
  const pendingRows = (status?.rows ?? []).filter((r) => !r.confirmed);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setErr("");
    try { await fn(); loadRounds(); loadStatus(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><LockOutlined style={{ marginRight: 8 }} />Chốt số liệu đơn vị</h2>
          <p>
            Phát yêu cầu <b>chốt số liệu đến một ngày</b> cho toàn bộ đơn vị thành viên và theo dõi
            đơn vị nào đã xác nhận. Đơn vị xác nhận xong thì <b>không tự sửa</b> số liệu thu mua ·
            tiêu thụ · tồn kho của những ngày đã chốt — chuyên viên và quản trị vẫn sửa hộ được.
          </p>
        </div>
        {isAdmin && (
          <div className="actions">
            <button className="btn btn-primary" onClick={() => setForm({ initial: null })}>
              <PlusOutlined /> Yêu cầu chốt số liệu
            </button>
          </div>
        )}
      </div>

      <div className="blt-toolbar">
        <label className="form-field">Đợt chốt
          <select className="blt-date-input" value={roundId ?? ""}
            onChange={(e) => setRoundId(Number(e.target.value) || null)}>
            {rounds.map((r) => (
              <option key={r.id} value={r.id}>
                Đến hết {dmy(r.lock_date)}{r.cancelled_at ? " (đã huỷ)" : ""} — {r.locked ?? 0} đơn vị đã chốt
              </option>
            ))}
            {!rounds.length && <option value="">Chưa có đợt chốt nào</option>}
          </select>
        </label>
        <label className="form-field">Tìm đơn vị
          <input className="blt-date-input" value={q} placeholder="Gõ tên đơn vị"
            onChange={(e) => setQ(e.target.value)} />
        </label>
        <label className="form-field" style={{ justifyContent: "flex-end" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 6, height: 34 }}>
            <input type="checkbox" checked={onlyPending}
              onChange={(e) => setOnlyPending(e.target.checked)} />
            Chỉ đơn vị <b>chưa xác nhận</b>
          </span>
        </label>
        <span style={{ alignSelf: "center", fontSize: 13 }}>
          {status?.round
            ? <>Đã xác nhận <b>{status.confirmed}</b>/{status.total} đơn vị</>
            : "Chưa có đợt chốt"}
        </span>
        <button className="btn" onClick={() => { loadRounds(); loadStatus(); }}>
          <ReloadOutlined /> Làm mới
        </button>
      </div>

      {round && isAdmin && (
        <div className="card" style={{ padding: 12, marginBottom: 12, display: "flex",
          flexWrap: "wrap", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 13 }}>
            Đợt <b>đến hết {dmy(round.lock_date)}</b>
            {round.note && <> · <i>{round.note}</i></>}
            {round.cancelled_at && <> · <b>đã huỷ {stamp(round.cancelled_at)}</b></>}
          </span>
          <span style={{ flex: 1 }} />
          <button className="btn" disabled={busy} onClick={() => setForm({ initial: round })}>
            Sửa ngày / lời nhắn
          </button>
          <button className="btn" disabled={busy || !pendingRows.length}
            title="Khoá hộ mọi đơn vị chưa xác nhận trong bộ lọc hiện tại"
            onClick={() => act(() => lockUnits(round.id, pendingRows.map((r) => r.company)))}>
            <LockOutlined /> Khoá hộ {pendingRows.length} đơn vị chưa xác nhận
          </button>
          <button className="btn" disabled={busy}
            onClick={() => act(() => cancelLockRound(round.id, !round.cancelled_at))}>
            {round.cancelled_at ? "Bỏ huỷ đợt" : "Huỷ đợt (mở lại số liệu)"}
          </button>
          <button className="btn" disabled={busy} title="Xoá hẳn đợt chốt (kèm mọi xác nhận)"
            onClick={() => act(() => deleteLockRound(round.id).then(() => setRoundId(null)))}>
            <DeleteOutlined />
          </button>
        </div>
      )}

      {err && <div className="blt-error" style={{ marginBottom: 10 }}>{err}</div>}

      <div className="card table-scroll" style={{ padding: 0 }}>
        <table>
          <thead><tr>
            <th style={{ minWidth: 260 }}>Đơn vị</th>
            <th style={{ width: 150 }}>Khu vực</th>
            <th style={{ width: 150 }}>Trạng thái</th>
            <th style={{ width: 170 }}>Thời điểm xác nhận</th>
            <th style={{ width: 170 }}>Người xác nhận</th>
            <th className="r" style={{ width: 120 }}>Thu mua (tấn)</th>
            <th className="r" style={{ width: 120 }}>Tiêu thụ (tấn)</th>
            <th className="r" style={{ width: 120 }}>Tồn kho (tấn)</th>
            <th style={{ width: 190 }}>Thao tác</th>
          </tr></thead>
          <tbody>
            {(status?.rows ?? []).map((r) => (
              <tr key={r.company}>
                <td>
                  {r.company}
                  {/* Đơn vị đã sáp nhập không đứng dòng riêng (không còn ai để đốc thúc) — ghi
                      trong dòng đơn vị nhận, vì đơn vị nhận bấm chốt là chốt kèm luôn phần này. */}
                  {r.merged_units.length > 0 && (
                    <div style={{ fontSize: 11, color: "var(--muted)" }}>
                      gồm {r.merged_units.map((m) => m.company).join(", ")} (đã sáp nhập)
                    </div>
                  )}
                </td>
                <td>{r.region ?? "—"}</td>
                <td>
                  {r.confirmed
                    ? <span style={{ color: "var(--accent-2)" }}>
                        <CheckCircleFilled /> Đã chốt{r.by_admin ? " (Ban khoá)" : ""}
                      </span>
                    : r.confirmed_at
                      // Đơn vị nhận đã chốt (trước khi có chốt kèm) nhưng phần đơn vị cũ thì chưa —
                      // đơn vị bấm lại ở banner, hoặc Ban khoá hộ dòng này, là chốt nốt phần đó.
                      ? <span style={{ color: "var(--warn, #d48806)" }}
                          title={"Chưa chốt: " + r.merged_units.filter((m) => !m.confirmed)
                            .map((m) => m.company).join(", ")}>
                          <WarningFilled /> Còn phần đã sáp nhập
                        </span>
                      : <span style={{ color: "var(--danger)" }}>
                          <WarningFilled /> Chưa xác nhận
                        </span>}
                </td>
                <td>{stamp(r.confirmed_at)}</td>
                <td>{r.confirmed_by ?? "—"}</td>
                {/* Ảnh chụp của đơn vị nhận sáp nhập đã là số GỘP — không cộng thêm đơn vị cũ. */}
                <td className="r">{n3(r.snapshot?.purchase?.total_purchase)}</td>
                <td className="r">{n3(r.snapshot?.consumption?.total_consumption)}</td>
                <td className="r">{n3(r.snapshot?.stock?.stock_finished as number)}</td>
                <td>
                  <button className="btn" disabled={!round}
                    onClick={() => round && setView({ company: r.company, roundId: round.id })}>
                    Xem số
                  </button>
                  {/* Dòng "còn phần đã sáp nhập" (đơn vị nhận đã chốt, đơn vị cũ chưa) có CẢ hai nút:
                      khoá hộ để chốt nốt phần cũ, hoặc mở khoá cả cặp cho đơn vị làm lại. */}
                  {isAdmin && round && !round.cancelled_at && r.confirmed_at && (
                    <button className="btn" disabled={busy} style={{ marginLeft: 6 }}
                      title="Mở khoá để đơn vị nhập bù / sửa (kèm đơn vị đã sáp nhập)"
                      onClick={() => act(() => unlockUnits(round.id, [r.company]))}>
                      <UnlockOutlined />
                    </button>
                  )}
                  {isAdmin && round && !round.cancelled_at && !r.confirmed && (
                    <button className="btn" disabled={busy} style={{ marginLeft: 6 }}
                      title="Khoá hộ đơn vị này (kèm đơn vị đã sáp nhập)"
                      onClick={() => act(() => lockUnits(round.id, [r.company]))}>
                      <LockOutlined />
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!status?.rows.length && (
              <tr><td colSpan={9} style={{ padding: 16, color: "var(--muted)" }}>
                {status?.round ? "Không có đơn vị nào khớp bộ lọc." : "Chưa có đợt chốt số liệu nào."}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {form && (
        <RoundForm initial={form.initial} onClose={() => setForm(null)}
          onSaved={() => { loadRounds(); loadStatus(); }} />
      )}
      {view && (
        <DataLockConfirmModal company={view.company} roundId={view.roundId} readOnly
          onClose={() => setView(null)} />
      )}
    </div>
  );
}
