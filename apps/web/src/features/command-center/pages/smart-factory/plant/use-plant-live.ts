/* Số mới nhất của khu đang mở (+ tag điện), hỏi lại mỗi `POLL_MS`. Server cache ngắn dùng chung nên
   nhiều người xem không dồn SCADA. Lỗi → giữ số cũ (mờ) + cờ `failed`; 429 (SCADA đang bận) → im lặng
   thử lại nhịp sau; 404 (nhà máy vừa bị tắt/gỡ sơ đồ) → ngừng hỏi + `onGone` để tải lại danh sách.
   Đổi khu: thanh điện giữ số cũ (tag điện chung mọi khu), sơ đồ chờ số của khu mới. */

import { useState } from "react";

import { ApiError } from "../../../../../lib/http";
import { type PlantValues, fetchPlantLive } from "../../../../../lib/smart-factory-client";
import { useVisiblePoll } from "../use-visible-poll";

const POLL_MS = 5_000;

type Live = { factoryId: number; area: string; values: PlantValues; fetchedAt: string | null };

export function usePlantLive(factoryId: number | null, area: string | null, onGone: () => void) {
  const [live, setLive] = useState<Live | null>(null);
  // Lỗi gắn với khu đã lỗi → đổi khu thì thôi báo lỗi cũ, chờ kết quả của khu mới.
  const [failedKey, setFailedKey] = useState<string | null>(null);
  const [goneKey, setGoneKey] = useState<string | null>(null);
  const key = factoryId != null && area ? `${factoryId}|${area}` : null;

  useVisiblePoll(async (alive) => {
    if (factoryId == null || !area) return undefined;
    try {
      const d = await fetchPlantLive(factoryId, area);
      if (!alive()) return undefined;
      setLive({ factoryId, area, values: d.values ?? {}, fetchedAt: d.fetched_at ?? null });
      setFailedKey(null);
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      if (!alive() || status === 429) return undefined;
      setFailedKey(key);
      if (status === 404) {
        setGoneKey(key);
        onGone();
      }
    }
    return undefined;
  }, POLL_MS, key !== goneKey ? key : null);

  const same = live?.factoryId === factoryId ? live : null;
  const mine = same && same.area === area ? same : null;
  return {
    /** Số của ĐÚNG khu đang mở — null khi chưa đọc xong lần đầu. */
    values: mine?.values ?? null,
    /** Giờ máy chủ trả lời lượt đọc đó (so với `at` để biết số cũ). */
    fetchedAt: mine?.fetchedAt ?? null,
    /** Số gần nhất của nhà máy (khu nào cũng có tag điện) — cho thanh điện. */
    powerValues: same?.values ?? null,
    failed: key != null && failedKey === key,
  };
}
