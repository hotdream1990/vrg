/* Tiện ích tuần ISO (Thứ 2 đầu tuần) cho báo cáo tuần đơn vị. Nội bộ giữ 'YYYY-MM-DD'. */

const p2 = (x: number) => String(x).padStart(2, "0");
const toISO = (d: Date) => `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
const parse = (iso: string) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); };

/** ISO date → ngày Thứ 2 của tuần chứa nó ('YYYY-MM-DD'). */
export const mondayOf = (iso: string): string => {
  const d = parse(iso);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return toISO(d);
};

/** Dịch `delta` tuần từ một week_key (Thứ 2). */
export const shiftWeeks = (weekKey: string, delta: number): string => {
  const d = parse(weekKey);
  d.setDate(d.getDate() + delta * 7);
  return toISO(d);
};

/** Khoảng ngày của tuần: { start=Thứ 2, end=Chủ nhật }. */
export const weekRange = (weekKey: string): { start: string; end: string } => {
  const e = parse(weekKey);
  e.setDate(e.getDate() + 6);
  return { start: weekKey, end: toISO(e) };
};

/** Số tuần ISO của một week_key (Thứ 2). */
export const isoWeekNo = (weekKey: string): number => {
  const target = parse(weekKey);
  target.setDate(target.getDate() + 3); // Thứ 5 cùng tuần quyết định số tuần ISO
  const firstThursday = new Date(target.getFullYear(), 0, 4);
  const diff = target.getTime() - firstThursday.getTime();
  return 1 + Math.round(diff / (7 * 24 * 3600 * 1000));
};

/** N week_key gần nhất (mới → cũ) tính từ `todayWeek`. */
export const recentWeeks = (todayWeek: string, count: number): string[] =>
  Array.from({ length: count }, (_, i) => shiftWeeks(todayWeek, -i));

const dm = (iso: string) => { const [, m, d] = iso.split("-"); return `${d}/${m}`; };

/** Nhãn tuần hiển thị: 'Tuần NN (dd/mm–dd/mm)'. */
export const weekLabel = (weekKey: string): string => {
  const r = weekRange(weekKey);
  return `Tuần ${isoWeekNo(weekKey)} (${dm(r.start)}–${dm(r.end)})`;
};
