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

/** Hôm nay dạng YYYY-MM-DD (cho state ô nhập ngày). */
export const todayISO = (): string => new Date().toISOString().slice(0, 10);
