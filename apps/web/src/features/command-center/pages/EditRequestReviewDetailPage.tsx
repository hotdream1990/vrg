import { ArrowLeftOutlined, CheckOutlined, CloseOutlined, FileSearchOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, App, Spin } from "antd";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { dmy } from "../../../lib/date";
import {
  type EditRequestDetail, approveEditRequest, fetchEditRequestDetail, rejectEditRequest,
} from "../../../lib/edit-request-client";
import EditRequestDiffTable from "../components/EditRequestDiffTable";
import EditRequestInfo from "../components/EditRequestInfo";
import EditRequestReviewModal from "../components/EditRequestReviewModal";
import "../edit-request.css";

const BACK = "/duyet-de-nghi-sua";

/** Chi tiết 1 đề nghị sửa số liệu phía Ban: thông tin · ảnh hưởng chốt · bảng Lúc gửi/Hiện tại/Đề nghị · Duyệt/Từ chối. */
export default function EditRequestReviewDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const { message } = App.useApp();
  const reqId = Number(id);

  const [data, setData] = useState<EditRequestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [actionErr, setActionErr] = useState("");
  const [mode, setMode] = useState<"approve" | "reject" | null>(null);

  const load = useCallback(() => {
    if (!Number.isFinite(reqId)) { setErr("Đường dẫn không hợp lệ."); setLoading(false); return; }
    setLoading(true); setErr("");
    fetchEditRequestDetail(reqId)
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [reqId]);
  useEffect(() => { load(); }, [load]);

  // Gửi kèm `updated_at` của bản ĐANG HIỂN THỊ: đơn vị vừa cập nhật đề nghị thì server trả 409, không
  // duyệt nhầm nội dung Ban chưa xem.
  const submit = async (note: string, acceptChanged: boolean) => {
    if (!data) return;
    const expected_updated_at = data.request.updated_at;
    setActionErr("");
    try {
      if (mode === "approve") {
        await approveEditRequest(reqId, { note, expected_updated_at, accept_changed: acceptChanged });
        message.success("Đã duyệt — số liệu đã được ghi.");
      } else {
        await rejectEditRequest(reqId, { note, expected_updated_at });
        message.success("Đã từ chối đề nghị.");
      }
    } catch (e) {
      // Duyệt lỗi (số liệu không hợp lệ, xung đột…) — đề nghị VẪN chờ duyệt; Ban đọc lỗi rồi quyết.
      setActionErr((e as Error).message);
    }
    setMode(null);
    load();
  };

  if (loading && !data) {
    return <div className="main"><div className="blt-loading"><Spin /> Đang tải…</div></div>;
  }
  if (!data) {
    return (
      <div className="main">
        <div className="blt-error">{err || "Không tìm thấy đề nghị."}</div>
        <button className="btn" onClick={() => nav(BACK)}><ArrowLeftOutlined /> Về danh sách</button>
      </div>
    );
  }

  const { request: r, current, lock } = data;
  const pending = r.status === "pending";
  const moveTarget = r.op === "daily_move" && Boolean((current ?? r.before)?.to_date_has_entry);

  return (
    <div className="main er-page">
      <div className="page-title">
        <div>
          <h2><FileSearchOutlined style={{ marginRight: 8 }} />{r.title}</h2>
          <p>Đề nghị sửa số liệu #{r.id} · {r.company}</p>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => nav(BACK)}><ArrowLeftOutlined /> Danh sách</button>
          <button className="btn" onClick={load}><ReloadOutlined /> Tải lại</button>
          {pending && (
            <>
              <button className="btn" onClick={() => setMode("reject")}><CloseOutlined /> Từ chối</button>
              <button className="btn btn-primary" onClick={() => setMode("approve")}><CheckOutlined /> Duyệt</button>
            </>
          )}
        </div>
      </div>

      {err && <div className="blt-error">{err}</div>}
      {actionErr && (
        <Alert type="error" showIcon closable style={{ marginBottom: 12 }} onClose={() => setActionErr("")}
          message="Không thực hiện được" description={actionErr} />
      )}
      {pending && data.changed_since_submit && (
        <Alert type="warning" showIcon style={{ marginBottom: 12 }}
          message="Số liệu đã thay đổi kể từ lúc đơn vị gửi đề nghị"
          description="So kỹ cột Hiện tại với cột Đề nghị trước khi duyệt — duyệt sẽ ghi đè bằng nội dung đề nghị." />
      )}
      {/* `null` = server không kiểm được (vd tài khoản người gửi bị khoá) — không khẳng định gì. */}
      {pending && data.still_blocked === false && (
        <Alert type="info" showIcon style={{ marginBottom: 12 }}
          message="Bản ghi này hiện không còn bị khoá — đơn vị đã tự sửa được trực tiếp." />
      )}

      <div className="card er-section">
        <EditRequestInfo request={r} />
      </div>

      <div className="card er-section">
        <h3>Ảnh hưởng chốt số liệu</h3>
        <div>
          {lock.locked_until
            ? <>Đơn vị đã chốt số liệu đến hết <b>{dmy(lock.locked_until)}</b>.</>
            : "Đơn vị chưa có đợt chốt số liệu nào đang hiệu lực."}
        </div>
        {pending && (lock.will_unlock.length > 0 ? (
          <div className="form-note">
            Duyệt sẽ gỡ xác nhận chốt của đơn vị ở đợt chốt đến hết{" "}
            <b>{lock.will_unlock.map((u) => dmy(u.lock_date)).join(", ")}</b> — đơn vị phải xác nhận chốt lại.
          </div>
        ) : <div>Duyệt không gỡ đợt chốt nào.</div>)}
        {moveTarget && <div className="form-note">Ngày chuyển đến đã có số liệu của biểu này.</div>}
      </div>

      <div className="card er-section">
        <h3>Nội dung thay đổi</h3>
        <EditRequestDiffTable request={r} current={current} withCurrent canOpenFiles labels={data.labels} />
      </div>

      {mode && (
        <EditRequestReviewModal mode={mode} request={r} willUnlock={lock.will_unlock}
          changedSinceSubmit={data.changed_since_submit}
          onSubmit={submit} onClose={() => setMode(null)} />
      )}
    </div>
  );
}
