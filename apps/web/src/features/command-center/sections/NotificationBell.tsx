/* Chuông thông báo ở header (chốt 01/10/2026) — đơn vị (nhập liệu · lãnh đạo) và Tập đoàn.

   Số trên chuông = luồng Hỗ trợ & Thông báo chưa đọc + đề nghị sửa chờ duyệt (người duyệt). Bấm mở
   bảng tin mới nhất; đáy bảng là công tắc Web Push của máy này (ẩn khi đang đăng nhập hộ — máy là
   của quản trị viên). Tải lại: mỗi 60 s khi tab đang hiện · khi đổi màn · khi vừa ghi vào hộp thư/
   đề nghị sửa · khi service worker báo có push mới. Tài khoản KHÔNG có chuông vẫn gắn component
   này (trả về rỗng) để nhận lệnh chuyển trang khi bấm thông báo và gỡ push còn sót của người trước. */

import { BellOutlined } from "@ant-design/icons";
import { Badge, Button, Empty, Popover, Spin, Tag } from "antd";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { DATA_SAVED_EVENT } from "../../../lib/http";
import {
  detachPush, isLocalPath, onServiceWorkerMessage, syncPushSubscription,
} from "../../../lib/push-client";
import { type ThreadRow, fetchSupportUnread, fetchThreads } from "../../../lib/support-client";
import { useAuth } from "../../auth/AuthContext";
import { useVisiblePoll } from "../pages/smart-factory/use-visible-poll";
import { useUnsavedGuard } from "../unsaved-guard";
import NotificationPushSwitch from "./NotificationPushSwitch";
import { KIND_COLOR, KIND_LABEL, stampVN } from "./support-format";
import "./notification-bell.css";

type Props = {
  /** Số đề nghị sửa chờ duyệt — khung đã tải cho Badge menu, chuông dùng lại (không tải 2 lần). */
  pendingEdits: number;
  /** Tài khoản duyệt đề nghị sửa (Tập đoàn, có quyền `edit_request`). */
  canReview: boolean;
  /** Service worker báo có push mới → nhờ khung tải lại số đề nghị chờ duyệt. */
  onPushed?: () => void;
};

const POLL_MS = 60_000;
// Đổi màn rồi mới đếm lại: mở một luồng = đánh dấu đã đọc, đếm ngay thì số trên chuông còn cũ.
const NAV_SETTLE_MS = 1500;
const PANEL_ROWS = 8;
const WATCHED_PATHS = ["/api/support", "/api/edit-requests"];

export default function NotificationBell({ pendingEdits, canReview, onPushed }: Props) {
  const { user, isUnitAccount, can, isImpersonating } = useAuth();
  const nav = useNavigate();
  const { pathname } = useLocation();
  const guard = useUnsavedGuard(false);   // chỉ lấy hàm hỏi-trước-khi-rời của khung
  const hasInbox = isUnitAccount || can("support");
  const show = hasInbox || canReview;
  const username = user?.username ?? "";

  const [unread, setUnread] = useState(0);
  const [nonce, setNonce] = useState(0);
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<ThreadRow[] | null>(null);
  const bump = useCallback(() => setNonce((n) => n + 1), []);
  const onPushedRef = useRef(onPushed);
  useLayoutEffect(() => { onPushedRef.current = onPushed; });
  const [settledPath, setSettledPath] = useState(pathname);
  useEffect(() => {
    const t = window.setTimeout(() => setSettledPath(pathname), NAV_SETTLE_MS);
    return () => window.clearTimeout(t);
  }, [pathname]);

  useVisiblePoll(async (alive) => {
    if (!hasInbox) return undefined;
    try {
      const r = await fetchSupportUnread();
      if (alive()) setUnread(r.count);
    } catch { /* giữ số cũ, nhịp sau thử lại */ }
    return undefined;
  }, POLL_MS, show ? `${settledPath}|${nonce}` : null);

  useEffect(() => {
    if (!show) return undefined;
    const onSaved = (e: Event) => {
      const path = (e as CustomEvent<{ path?: string }>).detail?.path ?? "";
      if (WATCHED_PATHS.some((p) => path.startsWith(p))) bump();
    };
    window.addEventListener(DATA_SAVED_EVENT, onSaved);
    return () => window.removeEventListener(DATA_SAVED_EVENT, onSaved);
  }, [show, bump]);

  // Tin từ service worker: có push mới → tải lại số; bấm thông báo khi đã có tab mở → chuyển màn
  // trong SPA (qua hàng rào "chưa lưu" như menu). Trả lời "đã nhận" NGAY, không chờ người dùng trả
  // lời hộp thoại "chưa lưu": quá ~1 s service worker tải lại cả trang, mất phần đang soạn.
  useEffect(() => onServiceWorkerMessage((msg, reply) => {
    if (msg.type === "vrg-push") {
      bump();
      onPushedRef.current?.();
      return;
    }
    if (msg.type !== "vrg-navigate") return;
    const to = msg.url;
    if (!isLocalPath(to)) { reply({ ok: false }); return; }
    reply({ ok: true });
    guard(() => nav(to));
  }), [bump, guard, nav]);

  // Máy dùng chung: có chuông + đã cho phép → đăng ký lại ngầm cho tài khoản đang đăng nhập (không
  // bao giờ hỏi quyền; đã tự tắt thì gỡ); KHÔNG có chuông (không có công tắc để tự tắt) → gỡ đăng ký
  // còn sót của người dùng trước. Đăng nhập hộ: máy là của quản trị viên — không đụng.
  useEffect(() => {
    if (isImpersonating || !username) return;
    if (show) void syncPushSubscription(username);
    else void detachPush();
  }, [show, isImpersonating, username]);

  useEffect(() => {
    if (!open || !hasInbox) return undefined;
    let alive = true;
    fetchThreads({ unread_only: true, page_size: PANEL_ROWS })
      .then((r) => { if (alive) setRows(r.rows); })
      .catch(() => { if (alive) setRows([]); });
    return () => { alive = false; };
  }, [open, hasInbox, unread]);

  if (!show) return null;

  const reviewCount = canReview ? pendingEdits : 0;
  const total = unread + reviewCount;
  const go = (to: string) => {
    setOpen(false);
    guard(() => nav(to));
  };
  const empty = reviewCount === 0 && (!hasInbox || (rows !== null && rows.length === 0));

  const panel = (
    <div className="notif-panel">
      <div className="notif-head">Thông báo</div>
      <div className="notif-list">
        {reviewCount > 0 && (
          <button type="button" className="notif-row" onClick={() => go("/duyet-de-nghi-sua")}>
            <div className="notif-row-top"><Tag color="orange">Đề nghị sửa</Tag></div>
            <div className="notif-subject">{reviewCount} đề nghị sửa chờ duyệt</div>
          </button>
        )}
        {hasInbox && rows === null && <div className="notif-empty"><Spin size="small" /></div>}
        {hasInbox && rows?.map((t) => (
          <button key={t.id} type="button" className="notif-row" onClick={() => go(`/ho-tro/${t.id}`)}>
            <div className="notif-row-top">
              <Tag color={KIND_COLOR[t.kind] ?? "default"}>{KIND_LABEL[t.kind] ?? t.kind}</Tag>
              <span className="notif-time">{relativeTime(t.last_at)}</span>
            </div>
            <div className="notif-subject">{t.subject}</div>
            <div className="notif-meta">{t.company}</div>
          </button>
        ))}
        {empty && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Không có thông báo mới" />}
      </div>
      {hasInbox && (
        <div className="notif-foot">
          <Button type="link" size="small" onClick={() => go("/ho-tro")}>Xem tất cả</Button>
        </div>
      )}
      {!isImpersonating && <NotificationPushSwitch username={username} />}
    </div>
  );

  return (
    <Popover
      content={panel} trigger="click" placement="bottomRight" arrow={false}
      open={open} onOpenChange={setOpen} destroyOnHidden
    >
      <Badge count={total} size="small" overflowCount={99} offset={[-4, 4]}>
        <Button type="text" shape="circle" aria-label={total ? `Thông báo (${total} mới)` : "Thông báo"}
          icon={<BellOutlined style={{ fontSize: 18 }} />} />
      </Badge>
    </Popover>
  );
}

/** ISO → "vừa xong" · "5 phút trước" · "3 giờ trước" · "2 ngày trước"; quá 1 tuần thì ghi giờ ngày. */
function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return stampVN(iso);
  const minutes = Math.floor((Date.now() - t) / 60_000);
  if (minutes < 1) return "vừa xong";
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.floor(hours / 24);
  return days < 7 ? `${days} ngày trước` : stampVN(iso);
}
