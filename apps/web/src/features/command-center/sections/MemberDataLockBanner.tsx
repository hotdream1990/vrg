import { CheckCircleFilled, LockFilled, WarningFilled } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { type LockCurrent, fetchLockCurrent } from "../../../lib/data-lock-client";
import { DATA_SAVED_EVENT } from "../../../lib/http";
import DataLockConfirmModal from "./DataLockConfirmModal";

const dmy = (iso?: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

/**
 * Hàng cảnh báo CHỐT SỐ LIỆU trên mọi màn của tài khoản đơn vị (yêu cầu 25/08/2026).
 *
 * Gắn ở khung `AdminLayout` cạnh bảng nhắc việc — cùng lý do: đơn vị vào màn nào cũng phải thấy
 * Ban TTKD đang yêu cầu chốt đến ngày nào. Ba trạng thái:
 *   - chưa có đợt chốt         → không hiện gì
 *   - có đợt, chưa xác nhận    → hàng ĐỎ + nút "Xem số liệu & xác nhận chốt"
 *   - đã xác nhận              → hàng xám gọn, nhắc muốn sửa thì gửi Đề nghị sửa (kèm nút xem lại số)
 */
export default function MemberDataLockBanner() {
  const { pathname } = useLocation();
  const [data, setData] = useState<LockCurrent | null>(null);
  const [open, setOpen] = useState<{ company: string; readOnly: boolean } | null>(null);

  const load = useCallback(() => {
    fetchLockCurrent().then(setData).catch(() => setData(null));
  }, []);
  useEffect(() => { load(); }, [load, pathname]);
  useEffect(() => {
    window.addEventListener(DATA_SAVED_EVENT, load);
    return () => window.removeEventListener(DATA_SAVED_EVENT, load);
  }, [load]);

  const round = data?.round;
  if (!round || round.cancelled_at) return null;

  const pending = data.units.filter((u) => !u.confirmed);
  const done = data.units.filter((u) => u.confirmed);

  return (
    <>
      {pending.length > 0 && (
        <div className="dsn dsn-manual" style={{ margin: "12px 24px 0" }}>
          <div className="dsn-head" style={{ cursor: "default" }}>
            <span className="dsn-badge"><WarningFilled /> Yêu cầu chốt số liệu</span>
            <span className="dsn-tagline">
              Ban TTKD yêu cầu chốt số liệu <b>thu mua · tiêu thụ · tồn kho</b> đến hết ngày{" "}
              <b>{dmy(round.lock_date)}</b>. Vui lòng rà lại số rồi <b>xác nhận</b> —
              sau khi chốt, đơn vị <b>không tự sửa</b> số liệu của những ngày này nữa.
              {round.note && <> Lời nhắn: <i>{round.note}</i></>}
            </span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, padding: "0 14px 12px" }}>
            {pending.map((u) => (
              <button key={u.company} className="btn btn-primary"
                onClick={() => setOpen({ company: u.company, readOnly: false })}>
                Xem số liệu &amp; xác nhận chốt
                {data.units.length > 1 && <> — {u.company}</>}
              </button>
            ))}
          </div>
        </div>
      )}

      {done.length > 0 && (
        <div className="dsn dsn-auto" style={{ margin: "12px 24px 0" }}>
          <div className="dsn-head" style={{ cursor: "default" }}>
            <span className="dsn-badge"><CheckCircleFilled /> Đã chốt số liệu</span>
            <span className="dsn-tagline">
              {done.map((u) => (
                <span key={u.company} style={{ marginRight: 12 }}>
                  <LockFilled />{" "}
                  {data.units.length > 1 && <>{u.company}: </>}
                  đã chốt đến hết ngày <b>{dmy(u.locked_until ?? round.lock_date)}</b>
                  {u.by_admin && <> (Ban TTKD khoá)</>}
                  {" · "}
                  <a role="button" tabIndex={0} style={{ textDecoration: "underline", cursor: "pointer" }}
                    onClick={() => setOpen({ company: u.company, readOnly: true })}>
                    xem lại số đã chốt
                  </a>
                </span>
              ))}
              — cần điều chỉnh số liệu đã chốt, mở đúng bản ghi cần sửa và bấm <b>Đề nghị sửa</b> để gửi
              Ban duyệt (theo dõi ở{" "}
              <Link to="/de-nghi-sua" style={{ textDecoration: "underline" }}>Đề nghị sửa số liệu</Link>).
            </span>
          </div>
        </div>
      )}

      {open && (
        <DataLockConfirmModal company={open.company} roundId={round.id} readOnly={open.readOnly}
          onClose={() => setOpen(null)} onConfirmed={load} />
      )}
    </>
  );
}
