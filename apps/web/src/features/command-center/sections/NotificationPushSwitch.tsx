/* Công tắc "Nhận thông báo trên máy này" (Web Push) ở đáy bảng chuông thông báo.
   Bật = xin quyền của trình duyệt + đăng ký với server cho tài khoản đang đăng nhập; báo được cả khi
   đã đóng trang. iPhone/iPad chỉ dùng được sau khi "Thêm vào màn hình chính". */

import { App, Switch, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";

import { type PushState, disablePush, enablePush, pushState } from "../../../lib/push-client";

type Props = {
  /** Tài khoản đang đăng nhập — lựa chọn "tắt trên máy này" nhớ theo từng tài khoản. */
  username: string;
};

const HINT: Record<PushState, { text: string; note: boolean }> = {
  unsupported: { text: "Trình duyệt này không hỗ trợ thông báo đẩy.", note: false },
  "ios-home-screen": {
    text: "Trên iPhone/iPad: bấm nút Chia sẻ → “Thêm vào MH chính”, rồi mở VRG từ biểu tượng "
      + "đó để bật thông báo.",
    note: true,
  },
  denied: {
    text: "Bạn đã chặn thông báo — mở cài đặt trang của trình duyệt (biểu tượng cạnh địa chỉ web) "
      + "để cho phép lại.",
    note: true,
  },
  on: { text: "Máy này sẽ báo cả khi đã đóng trang.", note: false },
  off: { text: "Bật để máy báo ngay khi có tin mới, kể cả khi đã đóng trang.", note: false },
};

const LOCKED: PushState[] = ["unsupported", "ios-home-screen", "denied"];

export default function NotificationPushSwitch({ username }: Props) {
  const { message } = App.useApp();
  const [state, setState] = useState<PushState | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(() => {
    pushState().then(setState).catch(() => setState("unsupported"));
  }, []);
  useEffect(() => { reload(); }, [reload]);

  const toggle = async (on: boolean) => {
    setBusy(true);
    try {
      if (on) {
        await enablePush(username);   // xin quyền ngay trong cú bấm (Safari đòi)
        message.success("Đã bật thông báo trên máy này.");
      } else {
        await disablePush(username);
        message.info("Đã tắt thông báo trên máy này.");
      }
    } catch (e) {
      message.error((e as Error).message || "Không đổi được cài đặt thông báo.");
    } finally {
      setBusy(false);
      reload();
    }
  };

  const hint = state ? HINT[state] : null;
  return (
    <div className="notif-push">
      <div className="notif-push-row">
        <span>Nhận thông báo trên máy này</span>
        <Switch
          size="small"
          checked={state === "on"}
          loading={busy || state === null}
          disabled={state !== null && LOCKED.includes(state)}
          onChange={(v) => void toggle(v)}
          aria-label="Nhận thông báo trên máy này"
        />
      </div>
      {hint && (hint.note
        ? <div className="form-note notif-push-hint">{hint.text}</div>
        : <Typography.Text type="secondary" className="notif-push-hint" style={{ display: "block" }}>
          {hint.text}
        </Typography.Text>)}
    </div>
  );
}
