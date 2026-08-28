/* Cơ sở tính độ của ĐƠN GIÁ THU MUA — chốt 17/08/2026, KHÔNG còn cho người nhập chọn.
   Trước đây mủ chén có ô chọn TSC/DRC và mặc định TSC, nên phần lớn bản ghi bị gán nhầm nhãn.

     - mủ NƯỚC → đồng/độ TSC
     - mủ CHÉN → đồng/độ DRC
     - mủ DÂY  → đồng/độ DRC (chốt 28/08/2026)
     - mọi số "quy khô" trong hệ thống (sản lượng thu mua, tồn kho nguyên liệu, quy khô của hợp
       đồng bán) đều là DRC.

   Bản sao của `app/core/market_meta.py::PURCHASE_PRICE_UNIT` — sửa bên nào thì sửa cả hai. */

export const LATEX_PRICE_UNIT = "đồng/độ TSC";
export const CUP_PRICE_UNIT = "đồng/độ DRC";
export const LACE_PRICE_UNIT = "đồng/độ DRC";

/** Dạng ngắn cho chú thích biểu đồ / câu nhận định. */
export const LATEX_PRICE_UNIT_SHORT = "đ/độ TSC";
export const CUP_PRICE_UNIT_SHORT = "đ/độ DRC";
export const LACE_PRICE_UNIT_SHORT = "đ/độ DRC";

/** Nhãn nhắc "quy khô ở đây là DRC" — dùng cho hint của các ô quy khô. */
export const DRY_BASIS_HINT = "mọi số quy khô trong hệ thống đều tính theo DRC";
