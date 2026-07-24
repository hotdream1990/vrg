/** Định dạng chứng từ đính kèm được nhận (bộ Hợp đồng · phiếu xuất kho · hoá đơn · HĐ tồn kho).
 *
 *  PHẢI KHỚP `_TYPES` trong `apps/api/app/services/contract_files.py` — server mới là nơi chốt,
 *  danh sách này chỉ để hộp thoại chọn file lọc sẵn cho đỡ chọn nhầm. Dùng ĐUÔI FILE thay vì
 *  kiểu MIME: trình duyệt khai MIME rất lệch nhau (HEIC của iPhone trên Windows thường về rỗng).
 */
export const CONTRACT_ACCEPT =
  ".pdf,.doc,.docx,.xls,.xlsx,.xml,.zip,.jpg,.jpeg,.png,.webp,.gif,.heic,.heif,.tif,.tiff";

/** Câu mô tả ngắn cho người nhập (khớp `ACCEPT_LABEL` phía server). */
export const CONTRACT_ACCEPT_LABEL =
  "PDF · Word · Excel · XML · ảnh (JPG, PNG, HEIC, WEBP, TIFF) · ZIP";

/** Giới hạn dung lượng mỗi file — khớp `_MAX_BYTES` phía server. */
export const CONTRACT_MAX_MB = 25;
