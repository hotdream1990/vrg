/* Giá thành SVR 3L quy từ giá mủ nước tư nhân — theo "Cách tính nhanh giá thành mủ" của chuyên viên:
     Giá thành SVR 3L (đồng/tấn) = Giá mủ (đồng/độ TSC) × hệ số × 100.000 + chi phí gia công chế biến
   · 100.000 = đổi "đồng/độ TSC" sang "đồng/tấn" (100 độ × 1.000 kg).
   · Hệ số với đơn vị tư nhân chốt 1,08 (khung tài liệu 1,08–1,1).
   · Chi phí gia công chế biến SVR 3L của công ty tư nhân 2.000.000–2.100.000 đồng/tấn → mặc định mức thấp,
     nhập lại được theo từng phiếu.
   Ví dụ tài liệu: 580 × 1,08 × 100.000 + 2.000.000 = 64.640.000 đồng/tấn. */

export const PRIVATE_SVR3L_COEF = 1.08;
export const DEFAULT_SVR3L_PROCESSING_COST = 2_000_000;
const TSC_TO_TONNE = 100_000;

/** Giá thành SVR 3L (đồng/tấn, làm tròn đồng) từ giá mủ đồng/độ TSC; null nếu chưa có giá. */
export const svr3lCost = (tscPrice: number | null | undefined, processingCost?: number | null): number | null =>
  tscPrice == null
    ? null
    : Math.round(tscPrice * PRIVATE_SVR3L_COEF * TSC_TO_TONNE + (processingCost ?? DEFAULT_SVR3L_PROCESSING_COST));
