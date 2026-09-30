/* Góc phải trên khung sơ đồ: giờ đọc mới nhất (chấm xanh nhấp nháy) — hoặc chấm xám + trạng thái ngắn
   khi mất kết nối · số cũ · đọc được nhưng không tag nào có số. Màn < 576px bỏ chữ "Cập nhật". */

import { hms } from "../smart-factory-format";

type Props = {
  /** Đã có kết quả đọc của khu đang mở. */
  loaded: boolean;
  /** Giờ đọc mới nhất trong các số (null = không tag nào có số). */
  at: string | null;
  failed: boolean;
  stale: boolean;
};

export default function PlantLiveStamp({ loaded, at, failed, stale }: Props) {
  const note = failed ? "Mất kết nối"
    : !loaded ? "Đang đọc…"
      : !at ? "Không có số"
        : stale ? `Số cũ ${hms(at)}` : null;
  const off = failed || stale || (loaded && !at);
  return (
    <span className="pl-stamp">
      <span className={`sf-live-dot${off ? " off" : ""}`} />
      {note ?? <><span className="pl-stamp-word">Cập nhật</span>{hms(at)}</>}
    </span>
  );
}
