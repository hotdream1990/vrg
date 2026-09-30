/* Số "tiêu thụ trong ngày" (Hôm qua / Hôm nay × Điện · Nước · Bành) cho Sơ đồ vận hành — dùng chung cho ô
   trên trang (PlantDailyUsage) và bảng trong khung sơ đồ (PlantUsageBox). Lấy phần chênh trong ngày (`used`)
   của API chỉ số theo ngày có sẵn, làm mới mỗi `DAILY_MS`. "Hôm nay" theo giờ Việt Nam (giờ nhà máy), không
   theo múi máy người xem. Lỗi → giữ số cũ + cờ `failed` (mờ); 429 → hỏi lại sớm. */

import dayjs from "dayjs";
import { useState } from "react";

import { ApiError } from "../../../../../lib/http";
import {
  type DailyMeters, type DailyRow, type MetricKey, fetchDailyMeters,
} from "../../../../../lib/smart-factory-client";
import { toISO } from "../smart-factory-format";
import { useVisiblePoll } from "../use-visible-poll";

const DAILY_MS = 60_000;
const BUSY_RETRY_MS = 5_000;
const FACTORY_TZ = "Asia/Ho_Chi_Minh";
const METRIC_ORDER: MetricKey[] = ["energy", "water", "bales"];

/** Ngày hôm nay theo giờ VN dạng YYYY-MM-DD ("sv-SE" in ngày đúng khuôn ISO). */
const vnToday = () => new Date().toLocaleDateString("sv-SE", { timeZone: FACTORY_TZ });

export type UsageRow = { label: string; row: DailyRow | undefined };

export function usePlantDailyUsage(factoryId: number, metrics: MetricKey[]) {
  const [data, setData] = useState<DailyMeters | null>(null);
  // Lỗi gắn với nhà máy đã lỗi → đổi nhà máy thì thôi báo lỗi cũ.
  const [failedId, setFailedId] = useState<number | null>(null);

  useVisiblePoll(async (alive) => {
    const today = vnToday();   // tính lại mỗi nhịp → qua nửa đêm tự sang ngày mới
    try {
      const d = await fetchDailyMeters(factoryId, toISO(dayjs(today).subtract(1, "day")), today);
      if (!alive()) return undefined;
      setData(d);
      setFailedId(null);
    } catch (e) {
      if (!alive()) return undefined;
      if (e instanceof ApiError && e.status === 429) return BUSY_RETRY_MS;
      setFailedId(factoryId);
    }
    return undefined;
  }, DAILY_MS, String(factoryId));

  const shown = data?.factory.id === factoryId ? data : null;
  const pick = (date?: string) => shown?.rows.find((r) => r.date === date);
  const rows: UsageRow[] = [
    { label: "Hôm qua", row: pick(shown?.date_from) },
    { label: "Hôm nay", row: pick(shown?.date_to) },
  ];
  return {
    /** Cột theo thứ tự Điện · Nước · Bành, chỉ những chỉ số nhà máy có. */
    cols: METRIC_ORDER.filter((k) => metrics.includes(k)),
    rows,
    failed: failedId === factoryId,
  };
}
