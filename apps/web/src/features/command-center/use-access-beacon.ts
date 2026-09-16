/* Báo cho server biết người dùng vừa vào trang nào (Lịch sử truy cập).
   Đặt ở AdminLayout — nơi MỌI màn sau đăng nhập đi qua — nên thêm trang mới không phải nhớ gì.
   Chỉ gửi ĐƯỜNG DẪN; tên trang do server ánh xạ (xem `core/access_meta.py`). */

import { useEffect, useRef } from "react";

import { trackPageView } from "../../lib/access-log-client";

export function useAccessBeacon(pathname: string, enabled: boolean): void {
  const lastSent = useRef("");
  useEffect(() => {
    if (!enabled || !pathname || pathname === lastSent.current) return;
    lastSent.current = pathname;
    trackPageView(pathname);
  }, [pathname, enabled]);
}
