/* Chặn rời trang khi còn thay đổi chưa lưu — cơ chế nhỏ dùng chung.
   App dùng <BrowserRouter> (không có `useBlocker` của data router) nên khung AdminLayout tự hỏi lại
   trước khi điều hướng menu / hồ sơ / đăng xuất; màn nào có form thì gọi `useUnsavedGuard(dirty)`.
   Đóng tab / tải lại trang: `beforeunload` (trình duyệt tự hiện hộp hỏi).
   HẠN CHẾ: nút Back/Forward của trình duyệt KHÔNG bị chặn. */

import { App } from "antd";
import { type ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useRef } from "react";

const DEFAULT_MESSAGE = "Các thay đổi chưa lưu sẽ mất.";

type GuardCtx = {
  /** Màn đăng ký lời nhắc khi đang có thay đổi chưa lưu (null = gỡ). */
  setBlocker: (message: string | null) => void;
  /** Chạy `action` ngay nếu không có gì chưa lưu; còn thì hỏi lại trước. */
  guard: (action: () => void) => void;
};

const UnsavedGuardContext = createContext<GuardCtx | null>(null);

/** Đặt ở khung (AdminLayout): trả `value` cho Provider + `guard` để bọc các thao tác rời trang. */
export function useUnsavedGuardHost(): GuardCtx {
  const { modal } = App.useApp();
  const blocker = useRef<string | null>(null);

  const setBlocker = useCallback((message: string | null) => { blocker.current = message; }, []);
  const guard = useCallback((action: () => void) => {
    const message = blocker.current;
    if (!message) { action(); return; }
    modal.confirm({
      title: "Rời trang khi chưa lưu?", content: message,
      okText: "Rời trang", cancelText: "Ở lại", okButtonProps: { danger: true },
      onOk: () => { blocker.current = null; action(); },
    });
  }, [modal]);

  return useMemo(() => ({ setBlocker, guard }), [setBlocker, guard]);
}

export function UnsavedGuardProvider({ value, children }: { value: GuardCtx; children: ReactNode }) {
  return <UnsavedGuardContext.Provider value={value}>{children}</UnsavedGuardContext.Provider>;
}

/** Màn có form gọi khi `dirty`: đăng ký với khung + bật `beforeunload`. Trả `guard` để bọc nút rời
 *  trang của chính màn (ngoài khung thì chạy thẳng). */
export function useUnsavedGuard(active: boolean, message = DEFAULT_MESSAGE): (action: () => void) => void {
  const ctx = useContext(UnsavedGuardContext);

  useEffect(() => {
    if (!active) return;
    ctx?.setBlocker(message);
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => {
      ctx?.setBlocker(null);
      window.removeEventListener("beforeunload", warn);
    };
  }, [ctx, active, message]);

  return ctx?.guard ?? ((action) => action());
}
