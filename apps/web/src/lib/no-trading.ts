/** Quy ước dùng chung: GIÁ 0 = phiên đó sàn KHÔNG GIAO DỊCH (No Trading).
 *
 *  Sàn nghỉ / không ra settlement thì giá là 0 — KHÔNG phải "giá bằng 0 USD", và tuyệt đối
 *  không lấy giá phiên trước đắp vào (xem `services/crawlers/.../sgx_sicom.py`). Số 0 vào kho
 *  giá từ 2 đường: file chính thức của sàn (SGX SETTLE=0, OSE không kỳ hạn nào giao dịch) và
 *  chuyên viên tự đưa về 0 ở màn Quản lý số liệu.
 *
 *  Bản Python tương ứng: `services/bulletin/bulletin/convert.py` (NO_TRADING / is_no_trading).
 */

export const NO_TRADING_LABEL = "No Trading";
/** Dạng rút gọn cho lưới dày (Bảng tính giá) — luôn kèm `title={NO_TRADING_LABEL}`. */
export const NO_TRADING_SHORT = "NT";

export const isNoTrading = (v: number | null | undefined): boolean => v === 0;

/** Ô giá trong bản tin/bảng giá: chưa có số → "—", giá 0 → "No Trading". */
export const fmtPrice = (v: number | null | undefined, empty = "—"): string =>
  v == null ? empty : isNoTrading(v) ? NO_TRADING_LABEL : v.toLocaleString();
