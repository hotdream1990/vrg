/* Chữ HIỂN THỊ của bảng Kế hoạch năm: nhãn ngắn + đơn vị tính + gợi ý (hiện khi rê chuột vào biểu tượng ⓘ).
   Tách khỏi PLAN_FIELDS vì PLAN_FIELDS có tiêu đề dài, đủ nghĩa, dùng cho chốt số liệu / so sánh đề nghị sửa / nhật ký.
   Ngữ cảnh do TIÊU ĐỀ NHÓM mang (Khai thác · Thu mua · Hàng hóa…) nên nhãn dòng không lặp lại tên nhóm. */

export type RowUi = { label: string; uom: "tấn" | "tỷ đồng"; hint?: string };

/** Khoá = khoá ô (`PlanKey`) hoặc mã dòng tổng (`PlanTotalId`) — xem year-plan-sections.ts. */
export const ROW_UI: Record<string, RowUi> = {
  plan_exploit_tonnes: { label: "Kế hoạch khai thác", uom: "tấn", hint: "Gồm cả phần nhượng quyền." },

  plan_tonnes: {
    label: "Thu mua nguyên liệu", uom: "tấn",
    hint: "Mủ nước, mủ chén, mủ dây (quy khô). Kế hoạch > 0 thì đơn vị mới có màn Báo cáo thu mua; để trống hoặc 0 = không tổ chức thu mua.",
  },
  plan_goods_tonnes: {
    label: "Hàng hóa (thành phẩm mua ngoài)", uom: "tấn",
    hint: "Thành phẩm mua của đơn vị khác để bán lại. Không tính vào thu mua nguyên liệu.",
  },
  purchase_total: { label: "Tổng thu mua", uom: "tấn" },

  plan_process_exploit_tonnes: { label: "Mủ khai thác", uom: "tấn" },
  plan_process_purchase_tonnes: { label: "Mủ thu mua", uom: "tấn" },
  process_total: { label: "Tổng chế biến", uom: "tấn" },

  plan_consume_exploit_tonnes: { label: "Khai thác", uom: "tấn" },
  plan_consume_purchase_tonnes: { label: "Thu mua", uom: "tấn" },
  plan_consume_goods_tonnes: { label: "Hàng hóa", uom: "tấn" },
  consume_total: { label: "Tổng tiêu thụ", uom: "tấn" },

  plan_revenue_exploit_ty: { label: "Khai thác", uom: "tỷ đồng" },
  plan_revenue_purchase_ty: { label: "Thu mua", uom: "tỷ đồng" },
  plan_revenue_goods_ty: { label: "Hàng hóa", uom: "tỷ đồng" },
  revenue_total: {
    label: "Tổng doanh thu", uom: "tỷ đồng",
    hint: "Tự cộng từ ba mục trên. Đơn vị trước đây chỉ khai tổng sẽ hiện «số cũ» cho tới khi nhập mục con đầu tiên.",
  },

  plan_stock_exploit_tonnes: { label: "Khai thác", uom: "tấn" },
  plan_stock_purchase_tonnes: { label: "Thu mua", uom: "tấn" },
  plan_stock_goods_tonnes: { label: "Hàng hóa", uom: "tấn" },
  stock_total: { label: "Tổng tồn kho", uom: "tấn" },

  plan_sales_spot_tonnes: { label: "Tiêu thụ HĐ chuyến", uom: "tấn" },
  signed_lt_tonnes: { label: "HĐ dài hạn đã ký", uom: "tấn" },
  carry_lt_tonnes: { label: "HĐ dài hạn năm trước chuyển sang", uom: "tấn" },
  carry_spot_tonnes: { label: "HĐ chuyến năm trước chuyển sang", uom: "tấn" },
};

/** Gợi ý ở tiêu đề nhóm (khoá = tiêu đề nhóm trong PLAN_SECTIONS). */
export const SECTION_HINT: Record<string, string> = {
  "Tồn kho thành phẩm cuối năm": "Số dự kiến còn lại tại 31/12, không cộng dồn qua các tháng.",
};

/** Chú thích khi rê chuột vào nhãn của ô tổng (thuộc tính `title`, rẻ hơn Tooltip cho hàng trăm ô). */
export const TOTAL_TITLE = "Hệ thống tự cộng từ các mục con";
export const TOTAL_TITLE_LEGACY = "Số đã khai trước đây (chỉ có tổng). Nhập mục con đầu tiên thì tổng đổi thành tổng các mục con";
