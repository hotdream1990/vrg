/* Khối "Kế hoạch năm" trong bảng xác nhận chốt số liệu — kế hoạch năm CHỐT CÙNG ĐỢT (03/10/2026):
   xác nhận chốt là xác nhận luôn chỉ tiêu năm, chốt xong muốn đổi phải gửi «Đề nghị sửa». */

import type { LockSummary } from "../../../lib/data-lock-client";
import { PLAN_FIELDS } from "../pages/year-plan-fields";

const n3 = (v: unknown) =>
  (typeof v === "number" && Number.isFinite(v) ? v.toLocaleString("vi-VN", { maximumFractionDigits: 3 }) : "—");

export default function DataLockPlanBlock({ plan }: { plan: NonNullable<LockSummary["plan"]> }) {
  const empty = PLAN_FIELDS.every((f) => plan.values[f.key] == null);
  return (
    <div style={{ marginTop: 14 }}>
      <h4 style={{ margin: "0 0 6px" }}>Kế hoạch năm {plan.year} (chốt cùng đợt)</h4>
      <div style={{ fontSize: 11.5, color: "var(--muted)", marginBottom: 6 }}>
        Chỉ tiêu đơn vị đã khai ở màn Kế hoạch năm. Chốt xong, đơn vị không tự sửa kế hoạch năm {plan.year} — cần
        điều chỉnh thì gửi «Đề nghị sửa» để Ban duyệt.
      </div>
      {empty
        ? <div className="blt-error" style={{ fontSize: 12.5 }}>Chưa khai kế hoạch năm {plan.year} — nên nhập ở màn Kế hoạch năm trước khi chốt.</div>
        : (
          <div className="kpi-row ct-kpi">
            {PLAN_FIELDS.map((f) => (
              <div key={f.key} className="kpi">
                <div className="label">{f.short}</div>
                <div className="value">{n3(plan.values[f.key])}</div>
              </div>
            ))}
          </div>
        )}
    </div>
  );
}
