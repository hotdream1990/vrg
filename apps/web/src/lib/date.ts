/* Định dạng ngày dùng chung — hiển thị DD/MM/YYYY (chuẩn VN). Dữ liệu nội bộ giữ YYYY-MM-DD. */

/** ISO 'YYYY-MM-DD' (hoặc ISO datetime) → 'DD/MM/YYYY'. Rỗng → '—'; không hợp lệ → trả nguyên. */
export const dmy = (v?: string | null): string => {
  if (!v) return "—";
  const [y, m, d] = v.slice(0, 10).split("-");
  return y && m && d ? `${d}/${m}/${y}` : v;
};

/** ISO 'YYYY-MM-DD' (hoặc ISO datetime) → 'DD/MM' (nhãn biểu đồ / caption ngắn, chuẩn VN). */
export const dm = (v?: string | null): string => {
  if (!v) return "—";
  const [, m, d] = v.slice(0, 10).split("-");
  return m && d ? `${d}/${m}` : v;
};

/** Date → 'YYYY-MM-DD' theo giờ ĐỊA PHƯƠNG. KHÔNG dùng toISOString(): nó quy về UTC nên lệch 1 ngày
 *  vào sáng sớm ở VN (UTC+7) — làm ngày mặc định lùi về hôm trước. */
export const isoDate = (d: Date): string =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Hôm nay dạng YYYY-MM-DD (cho state ô nhập ngày) — theo giờ địa phương. */
export const todayISO = (): string => isoDate(new Date());

/** N ngày trước dạng YYYY-MM-DD — theo giờ địa phương. */
export const daysAgoISO = (n: number): string => {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return isoDate(d);
};

/** ISO datetime → 'HH:mm:ss DD/MM/YYYY' (dấu thời gian đầy đủ cho nhật ký). Rỗng → '—'. */
export const stampVN = (v?: string | null): string => {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())} ${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`;
};
