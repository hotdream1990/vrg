/* TRANG XEM THỬ cảnh báo nhập liệu — CHỈ CHẠY Ở CHẾ ĐỘ DEV (bản production chuyển hướng về trang chủ).
   Mục đích: xem giao diện cảnh báo mà không cần tài khoản. Số liệu bên dưới là CÁC CA SAI THẬT lấy
   từ production ngày 23–24/07/2026 (đơn giá nhập theo đồng/tấn, tồn kho nhập theo kg) — dựng lại để
   đối chiếu. Xoá file này cùng route trong App.tsx khi không cần nữa. */

import type { Values } from "../../../lib/unit-daily-fields";
import ConsumptionForm from "./ConsumptionForm";
import PurchaseForm from "./PurchaseForm";

/** Ca sai thật: đơn giá gõ theo ĐỒNG/tấn vào ô tính bằng TRIỆU đồng/tấn + dòng USD quên tỷ giá. */
const CONSUMPTION_SAMPLE = {
  sales_own: [
    { contract: "long_term", channel: "export", grade: "SVR 10 / CSR 10", qty: 210, price: 61_328_351, ccy: "VND" },
    { contract: "spot", channel: "domestic", grade: "SVR 3L", qty: 48.5, price: 49.85, ccy: "VND" },
    { contract: "long_term", channel: "export", grade: "SVR CV60", qty: 25, price: 1_880, ccy: "USD", fx: null },
  ],
  sales: [
    { contract: "long_term", channel: "export", grade: "SVR 10 / CSR 10", qty: 210, price: 57_730_558, ccy: "VND" },
  ],
  stock_warehoused: [
    { grade: "SVR 10 / CSR 10", qty: 737_099 },   // nhập theo kg thay vì tấn
    { grade: "SVR 3L", qty: 115.4 },              // số đúng — không cảnh báo
  ],
  stock_not_warehoused: [{ grade: "SVR 10 / CSR 10", qty: 206.82 }],
  stock_material: 177_577,
} as unknown as Values;

/** Ca sai của biểu Thu mua: sản lượng ngày nhập theo kg, đơn giá thành phẩm nhập theo đồng/tấn. */
const PURCHASE_SAMPLE = {
  latex_wet: 5_719,
  coagulum: 0.29,
  finished: [
    { grade: "SVR 10 / CSR 10", qty: 32.5, price: 52_400_000, ccy: "VND" },
    { grade: "SVR 3L", qty: 12, price: 51.2, ccy: "VND" },
  ],
} as unknown as Values;

const note = (t: string) => (
  <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 10 }}>{t}</div>
);

export default function EntryWarnPreview() {
  return (
    <div style={{ padding: 24, maxWidth: 1240, margin: "0 auto" }}>
      <div className="page-title">
        <div>
          <h2>Xem thử cảnh báo nhập liệu</h2>
          <p>
            Trang tạm để duyệt giao diện — chỉ có ở chế độ dev, không cần đăng nhập.
            Số liệu là các ca nhập sai có thật trên production ngày 23–24/07/2026.
          </p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 18 }}>
        <h3>Biểu Tiêu thụ – Tồn kho</h3>
        {note("Sai: 2 dòng đơn giá gõ theo đồng/tấn · 1 dòng USD quên tỷ giá · tồn kho nhập theo kg.")}
        <ConsumptionForm values={CONSUMPTION_SAMPLE} formKey="preview-consumption" />
      </div>

      <div className="card">
        <h3>Biểu Thu mua</h3>
        {note("Sai: sản lượng mủ nước nhập theo kg · đơn giá thành phẩm gõ theo đồng/tấn.")}
        <PurchaseForm values={PURCHASE_SAMPLE} formKey="preview-purchase" />
      </div>
    </div>
  );
}
