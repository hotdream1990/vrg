/* Định dạng số · giờ · cờ số liệu + kỳ xem cho màn Chỉ số điện · nước · số bành.
   null = CHƯA CÓ SỐ → luôn "—", không bao giờ quy về 0. Thời điểm là giờ nhà máy dạng
   `YYYY-MM-DDTHH:MM:SS` → cắt chuỗi, không qua `new Date()` (khỏi lệch múi giờ máy người xem). */

import dayjs, { type Dayjs } from "dayjs";

import { dmy } from "../../../../lib/date";
import type { MeterCell, MetricKey } from "../../../../lib/smart-factory-client";

/** Kỳ xem tối đa (khớp server — vượt thì server trả 400). */
export const MAX_DAYS = 92;

/** Số lẻ: chỉ số lũy kế giữ 3 số (điện = Wh/1000 nên chính xác tới 3 số lẻ), tiêu thụ 2 số, bành nguyên. */
const READING_DIGITS: Record<MetricKey, number> = { energy: 3, water: 3, bales: 0 };
const USED_DIGITS: Record<MetricKey, number> = { energy: 2, water: 2, bales: 0 };

/** Màu cột theo chỉ số (điện vàng · nước xanh dương · bành xanh lá VRG). */
export const METRIC_COLOR: Record<MetricKey, string> = {
  energy: "#f59e0b", water: "#0ea5e9", bales: "#16AF67",
};

const vi = (v: number, digits: number) =>
  v.toLocaleString("vi-VN", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const fmtNum = (v: number | null | undefined, digits: number): string =>
  (v == null ? "—" : vi(v, digits));

export const fmtReading = (v: number | null | undefined, key: MetricKey) =>
  fmtNum(v, READING_DIGITS[key] ?? 2);

export const fmtUsed = (v: number | null | undefined, key: MetricKey) =>
  fmtNum(v, USED_DIGITS[key] ?? 2);

/** Phần chênh trong ngày: điện/nước là "tiêu thụ", số bành là "sản lượng". */
export const usedWord = (key: MetricKey) => (key === "bales" ? "sản lượng" : "tiêu thụ");

/** Viết hoa chữ cái đầu ("tiêu thụ" → "Tiêu thụ"). */
export const upperFirst = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Câu lỗi hiển thị cho người dùng (ApiError đã mang `detail` tiếng Việt của server). */
export const errText = (e: unknown, fallback = "Thao tác không thành công, vui lòng thử lại.") =>
  (e instanceof Error && e.message ? e.message : fallback);

/** Ghép đơn vị sau số — chưa có số thì chỉ "—". */
export const withUnit = (text: string, unit: string) => (text === "—" ? text : `${text} ${unit}`);

/** "2026-09-30T15:39:00" → "15:39". */
export const hhmm = (ts?: string | null) => (ts ? ts.slice(11, 16) : "");

/** "2026-09-30T15:39:00" → "15:39 30/09/2026". */
export const stampLocal = (ts?: string | null) => (ts ? `${hhmm(ts)} ${dmy(ts)}` : "—");

/** Giờ máy SCADA KÈM múi: "2026-09-30T15:39:12+07:00" → "15:39:12 30/09/2026 (UTC+07:00)".
 *  Cắt chuỗi, giữ nguyên múi của máy SCADA (không quy đổi theo máy người xem). */
export function stampWithZone(ts?: string | null): string {
  const m = ts ? /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})?$/.exec(ts) : null;
  if (!m) return ts || "—";
  const zone = m[3] === "Z" ? "+00:00" : m[3];
  return `${m[2]} ${dmy(m[1])}${zone ? ` (UTC${zone})` : ""}`;
}

/** Mốc đúng 00:00 thì không cần ghi giờ ra bảng. */
export const isMidnight = (ts?: string | null) => !ts || ts.slice(11, 16) === "00:00";

/** Câu giải thích cờ của một ô (Tooltip trên bảng / biểu đồ). null = ô bình thường. */
export function flagText(cell?: MeterCell): string | null {
  if (!cell?.flag) return null;
  switch (cell.flag) {
    case "partial": {
      const at = [cell.open_at, cell.close_at].filter((t) => !isMidnight(t)).map(hhmm);
      return `Mốc 00:00 không có số — dùng số lúc ${at.join(" và ") || "gần nhất trong ngày"}`;
    }
    case "reset":
      return "Chỉ số bị giảm trong ngày (đồng hồ bị đặt lại hoặc đọc lỗi) — không tính tiêu thụ";
    case "no_data":
      return "Không có số liệu trong ngày";
    case "in_progress":
      return `Hôm nay — tính đến ${hhmm(cell.close_at) || "hiện tại"}`;
    default:
      return null;
  }
}

// ── Kỳ xem ──────────────────────────────────────────────────────────────────

export type Range = [Dayjs, Dayjs];

export const toISO = (d: Dayjs) => d.format("YYYY-MM-DD");

/** Số ngày của kỳ (tính cả 2 đầu). */
export const rangeDays = ([from, to]: Range) => to.startOf("day").diff(from.startOf("day"), "day") + 1;

const lastDays = (n: number): Range => [dayjs().subtract(n - 1, "day").startOf("day"), dayjs().startOf("day")];

/** Mặc định 30 ngày gần nhất tính cả hôm nay (khớp mặc định của server). */
export const defaultRange = (): Range => lastDays(30);

/** Preset của RangePicker — tính lại mỗi lần mở (qua nửa đêm vẫn đúng "hôm nay"). */
export const RANGE_PRESETS: { label: string; value: () => Range }[] = [
  { label: "7 ngày", value: () => lastDays(7) },
  { label: "30 ngày", value: () => lastDays(30) },
  { label: "90 ngày", value: () => lastDays(90) },
  { label: "Tháng này", value: () => [dayjs().startOf("month"), dayjs().startOf("day")] },
  {
    label: "Tháng trước",
    value: () => {
      const m = dayjs().subtract(1, "month");
      return [m.startOf("month"), m.endOf("month").startOf("day")];
    },
  },
];

/** Chặn chọn ngày tương lai. */
const isFutureDay = (d: Dayjs) => d.isAfter(dayjs(), "day");

/** `disabledDate` của RangePicker: chặn ngày tương lai + (khi đã chọn 1 đầu — `info.from`, AntD v6)
 *  chặn ngày cách đầu đó từ MAX_DAYS ngày trở lên → không thể chọn kỳ quá MAX_DAYS ngày. */
export const disabledRangeDate = (d: Dayjs, info: { type: string; from?: Dayjs }) =>
  isFutureDay(d)
  || (info.type === "date" && !!info.from
    && Math.abs(d.startOf("day").diff(info.from.startOf("day"), "day")) >= MAX_DAYS);

/** Câu báo lỗi kỳ (null = hợp lệ) — chặn ngay ở web, khỏi gọi SCADA vô ích. */
export function rangeError(r: Range): string | null {
  const n = rangeDays(r);
  if (n < 1) return "Khoảng ngày không hợp lệ: “từ ngày” đang sau “đến ngày”.";
  if (n > MAX_DAYS) {
    return `Kỳ xem tối đa ${MAX_DAYS} ngày — đang chọn ${n} ngày. Hãy thu hẹp khoảng ngày (vd chọn “90 ngày”).`;
  }
  return null;
}
