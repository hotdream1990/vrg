import { Tag } from "antd";

import { dmy } from "../../../lib/date";
import {
  EDIT_REQUEST_ACTION, type EditRequest, editRequestAction, statusMeta,
} from "../../../lib/edit-request-client";
import { stampVN } from "../sections/support-format";
import "../edit-request.css";

/** Khối thông tin một đề nghị sửa số liệu — dùng chung cho Drawer của đơn vị và trang duyệt của Ban. */
export default function EditRequestInfo({ request: r }: { request: EditRequest }) {
  const st = statusMeta(r.status);
  const reviewed = r.status === "approved" || r.status === "rejected";
  const action = EDIT_REQUEST_ACTION[editRequestAction(r)];
  return (
    <dl className="er-info">
      <dt>Đơn vị</dt>
      <dd><b>{r.company}</b></dd>
      <dt>Nội dung</dt>
      <dd>
        {r.title} <Tag style={{ marginLeft: 6 }}>{r.op_label}</Tag>
        <Tag color={action.color}>{action.label}</Tag>
      </dd>
      {r.dates.length > 0 && (<><dt>Ngày số liệu</dt><dd>{r.dates.map(dmy).join(" · ")}</dd></>)}
      <dt>Người gửi</dt>
      <dd>{r.requested_by_name || r.requested_by}</dd>
      <dt>Gửi lúc</dt>
      <dd>
        {stampVN(r.requested_at)}
        {/* Duyệt/từ chối/huỷ cũng đổi `updated_at` — chỉ đề nghị còn chờ mới là "đơn vị cập nhật nội dung". */}
        {r.status === "pending" && r.updated_at && r.updated_at !== r.requested_at
          && <> · cập nhật {stampVN(r.updated_at)}</>}
      </dd>
      <dt>Lý do chỉnh sửa</dt>
      <dd>{r.reason}</dd>
      {r.blocked.length > 0 && (
        <>
          <dt>Vì sao không tự sửa</dt>
          <dd><ul>{r.blocked.map((b) => <li key={b}>{b}</li>)}</ul></dd>
        </>
      )}
      <dt>Trạng thái</dt>
      <dd><Tag color={st.color}>{st.label}</Tag></dd>
      {reviewed && (
        <>
          <dt>{r.status === "approved" ? "Người duyệt" : "Người từ chối"}</dt>
          <dd>{r.reviewed_by_name || r.reviewed_by || "—"} · {stampVN(r.reviewed_at)}</dd>
        </>
      )}
      {r.review_note && (<><dt>Ghi chú của Ban</dt><dd>{r.review_note}</dd></>)}
      {r.unlocked && r.unlocked.length > 0 && (
        <>
          <dt>Chốt số liệu đã gỡ</dt>
          <dd>
            <span className="form-note">
              Đợt chốt đến hết {r.unlocked.map((u) => dmy(u.lock_date)).join(", ")} đã được gỡ — đơn vị
              rà lại số liệu rồi xác nhận chốt lần nữa (nút ở cảnh báo chốt số liệu trên đầu màn hình).
            </span>
          </dd>
        </>
      )}
    </dl>
  );
}
