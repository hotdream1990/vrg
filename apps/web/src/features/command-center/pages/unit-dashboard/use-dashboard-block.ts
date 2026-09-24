/* Tải MỘT khối số liệu của Dashboard đơn vị. Mỗi khối (thu mua · tiêu thụ · tồn kho · chỉ tiêu ·
   diễn biến tồn kho) tải độc lập: khối nào chậm/lỗi chỉ ảnh hưởng ô của nó, không chặn cả trang. */

import { useEffect, useState } from "react";

export type BlockState<T> = { data: T | null; loading: boolean; error: string | null };

const IDLE = { data: null, loading: false, error: null } as const;

/**
 * `load` phải là hàm ỔN ĐỊNH (khai ngoài component) và `query` phải được `useMemo` — nếu không
 * effect chạy lại mỗi lần render. `query = null` = chưa đủ điều kiện gọi (chưa có phạm vi, khoảng
 * ngày sai…) → khối về trạng thái trống. `tick` tăng = bấm "Tải lại".
 *
 * Chỉ nhận kết quả của lượt gọi MỚI NHẤT: đổi kỳ khi lượt trước chưa về thì lượt cũ bị bỏ (cờ
 * `alive` tắt khi effect dọn dẹp) — tránh nút kỳ ghi "Tháng trước" mà số lại của "Tháng này".
 * Xoá số cũ ngay khi bắt đầu tải: để số của kỳ trước nằm dưới nhãn kỳ mới là đọc nhầm chắc chắn.
 */
export function useDashboardBlock<T, Q>(
  load: (q: Q, signal?: AbortSignal) => Promise<T>, query: Q | null, tick: number,
): BlockState<T> {
  const [state, setState] = useState<BlockState<T>>(IDLE);

  useEffect(() => {
    if (!query) {
      setState(IDLE);
      return;
    }
    let alive = true;
    const ac = new AbortController();
    setState({ data: null, loading: true, error: null });
    load(query, ac.signal)
      .then((data) => { if (alive) setState({ data, loading: false, error: null }); })
      .catch((e: unknown) => {
        if (alive) setState({ data: null, loading: false,
                              error: e instanceof Error ? e.message : String(e) });
      });
    // Huỷ luôn request đang bay (server thôi tính lượt đã bị bỏ); lỗi AbortError rơi vào catch nhưng
    // `alive` đã tắt nên không đụng tới state.
    return () => { alive = false; ac.abort(); };
  }, [load, query, tick]);

  return state;
}
