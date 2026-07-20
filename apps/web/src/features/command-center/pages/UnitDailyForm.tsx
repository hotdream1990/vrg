/* Form nhập số liệu 1 đơn vị / 1 ngày — chọn form theo loại biểu:
   - Thu mua ("purchase") → PurchaseForm (bố trí theo loại mủ + quy đổi ngoại tệ).
   - Tiêu thụ–Tồn kho ("consumption") → ConsumptionForm (bảng nhiều dòng + tồn kho).
   Dùng chung: đơn vị thành viên nhập inline · chuyên viên sửa trong Modal. */

import type { PriceDraft, UnitPurchasePrice } from "../../../lib/unit-daily-client";
import type { Kind, Values } from "../../../lib/unit-daily-fields";
import ConsumptionForm, { type ConsumptionTab } from "./ConsumptionForm";
import PurchaseForm from "./PurchaseForm";

export type { PriceDraft };

type Props = {
  kind: Kind;
  values: Values;
  plan?: number | null;
  readOnly?: boolean;
  formKey: string;                // đổi khi đổi đơn vị/ngày/loại → reset nháp
  currency?: string;              // loại tiền đơn vị (VND/LAK/KHR)
  hasFactory?: boolean;           // có nhà máy? (Tiêu thụ: ẩn/hiện tồn kho nguyên liệu)
  role?: "member" | "hq";         // upload file HĐ đúng endpoint
  company?: string;               // đơn vị đang nhập (Tồn kho: nút "Lấy tồn ngày trước")
  day?: string;                   // ngày đang nhập  (Tồn kho: nút "Lấy tồn ngày trước")
  defaultTab?: ConsumptionTab;    // Tiêu thụ–Tồn kho: tab mở sẵn
  linkedPrice?: UnitPurchasePrice | null; // đơn giá mủ nước/mủ chén đúng ngày (Thu mua)
  onDirty?: (dirty: boolean) => void;
  footer?: (dirty: boolean, current: Values, prices: PriceDraft) => React.ReactNode;
};

export default function UnitDailyForm(
  { kind, values, readOnly, formKey, currency, hasFactory, role, company, day, defaultTab, linkedPrice, onDirty, footer }: Props,
) {
  if (kind === "purchase") {
    return (
      <PurchaseForm values={values} readOnly={readOnly} formKey={formKey}
        currency={currency} linkedPrice={linkedPrice} onDirty={onDirty} footer={footer} />
    );
  }
  return (
    <ConsumptionForm values={values} readOnly={readOnly} formKey={formKey}
      currency={currency} hasFactory={hasFactory} role={role} company={company} day={day}
      defaultTab={defaultTab} onDirty={onDirty} footer={footer} />
  );
}
