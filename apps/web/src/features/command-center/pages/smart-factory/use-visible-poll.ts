/* Hỏi server theo nhịp cho các màn Nhà máy thông minh: lần đầu LUÔN đọc (mở ở tab nền vẫn có số), các
   nhịp sau dừng khi tab ẩn và đọc ngay khi tab hiện lại. Nhịp sau chỉ hẹn khi lượt trước xong → không bao
   giờ chồng 2 lượt đọc lên SCADA dù SCADA chậm. Đổi `key` = đọc lại ngay; `key` null = ngừng hỏi. */

import { useEffect, useLayoutEffect, useRef } from "react";

/** `tick` tự xử lý lỗi; trả số ms tới nhịp sau (undefined = `ms`), vd hỏi lại sớm khi server bận.
 *  `alive()` false = `key` đã đổi / màn đã đóng trong lúc chờ → bỏ kết quả về muộn, đừng ghi state. */
export type PollTick = (alive: () => boolean) => Promise<number | undefined>;

export function useVisiblePoll(tick: PollTick, ms: number, key: string | null): void {
  const tickRef = useRef(tick);
  useLayoutEffect(() => { tickRef.current = tick; });

  useEffect(() => {
    if (key == null) return undefined;
    let timer: number | undefined;
    let running = false;
    let stopped = false;
    const alive = () => !stopped;

    const run = async (force = false) => {
      if (stopped || running) return;
      window.clearTimeout(timer);
      if (!force && document.hidden) return;   // tab ẩn: ngừng hẹn, hiện lại thì chạy tiếp
      running = true;
      let next: number | undefined;
      try { next = await tickRef.current(alive); } catch { /* tick tự xử lý lỗi */ }
      running = false;
      if (!stopped) timer = window.setTimeout(() => void run(), next ?? ms);
    };

    void run(true);
    const onShow = () => { if (!document.hidden) void run(); };
    document.addEventListener("visibilitychange", onShow);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onShow);
    };
  }, [key, ms]);
}
