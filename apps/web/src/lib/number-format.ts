/** Định dạng & đọc số kiểu vi-VN — 1 NGUỒN DUY NHẤT cho mọi ô nhập số.
 *
 *  Vì sao phải gom về đây: các ô nhập trước đây tự parse bằng `Number(s.replace(/[.,]/g, ""))`,
 *  tức XOÁ luôn dấu thập phân → bấm vào ô đang có 2.238,5 rồi rời đi là lưu thành 22.385
 *  (sai gấp 10 lần) mà người dùng không hề gõ gì. Ô nhập ghi thẳng vào kho giá nên sai ở
 *  đây là sai số liệu thật.
 */

const groupInt = (s: string) => s.replace(/\B(?=(\d{3})+(?!\d))/g, ".");

/** Số → chuỗi vi-VN "1.234,5" (GIỮ NGUYÊN phần thập phân, không làm tròn).
 *  Dùng để đổ giá trị vào ô lúc bắt đầu sửa → gõ xong parse lại ra đúng số cũ. */
export function formatViNumber(v?: string | number | null): string {
  if (v == null || v === "") return "";
  const s = String(v);
  const neg = s.startsWith("-") ? "-" : "";
  const [intp, dec] = s.replace("-", "").split(".");
  return neg + groupInt(intp || "0") + (dec != null ? `,${dec}` : "");
}

/** Chuỗi người dùng gõ → số (null nếu rỗng/không phải số).
 *
 *  Quy tắc (chấp nhận cả 2 lối viết để người dùng dán từ Excel Việt lẫn Anh đều đúng):
 *   - Có dấu phẩy  → phẩy là thập phân, chấm là phân cách nghìn:  "2.238,5" → 2238.5
 *   - Chỉ có chấm, đúng dạng nhóm nghìn                        :  "26.110"  → 26110
 *   - Chỉ có chấm, không phải dạng nhóm nghìn                   :  "163.12"  → 163.12
 */
export function parseViNumber(s?: string | null): number | null {
  const raw = (s ?? "").trim().replace(/\s/g, "");
  if (!raw) return null;
  let norm: string;
  if (raw.includes(",")) {
    norm = raw.replace(/\./g, "").replace(",", ".");
  } else if (/^-?\d{1,3}(\.\d{3})+$/.test(raw)) {
    norm = raw.replace(/\./g, "");
  } else {
    norm = raw;
  }
  const n = Number(norm);
  return isNaN(n) ? null : n;
}
