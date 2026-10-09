/* Khối "Kế hoạch năm" trong bảng xác nhận chốt số liệu — kế hoạch năm CHỐT CÙNG ĐỢT (03/10/2026):
   xác nhận chốt là xác nhận luôn chỉ tiêu năm, chốt xong muốn đổi phải gửi «Đề nghị sửa».
   Từ 09/10/2026 có 7 nhóm · 23 chỉ tiêu → bày dạng BẢNG GỌN hai cột theo đúng nhóm/nhãn của màn Kế hoạch
   năm (không dùng thẻ KPI: 23 thẻ to khó quét). Hiện CẢ ô chưa khai ("—") để đơn vị thấy còn thiếu gì
   trước khi bấm chốt; bản chụp cũ (trước 09/10) thiếu khoá mới thì chỉ hiện ô có số. */

import { ArrowRightOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";

import type { LockSummary } from "../../../lib/data-lock-client";
import type { YearPlanRow } from "../../../lib/unit-daily-client";
import { PLAN_FIELDS } from "../pages/year-plan-fields";
import { ROW_UI, SECTION_HINT } from "../pages/year-plan-labels";
import { PLAN_SECTIONS, PLAN_TOTALS, sectionRowId, totalInfo } from "../pages/year-plan-sections";
import "./data-lock-plan-block.css";

const n3 = (v: number) => v.toLocaleString("vi-VN", { maximumFractionDigits: 3 });
/** Khoá chỉ có từ 09/10/2026: có mặt trong snapshot = bản chụp mới. */
const NEW_KEY = "plan_process_exploit_tonnes";

type Props = {
  plan: NonNullable<LockSummary["plan"]>;
  /** Có = hiện liên kết «Mở màn Kế hoạch năm» (đơn vị đang xác nhận chốt); gọi để đóng bảng xác nhận. Không = chỉ xem. */
  onOpenPlan?: () => void;
};

/** Liên kết sang màn Kế hoạch năm để đơn vị vào nhập/sửa rồi quay lại chốt. */
function OpenPlanLink({ onOpen }: { onOpen: () => void }) {
  return (
    <Link to="/ke-hoach-nam" className="dlp-link" onClick={onOpen}>
      Mở màn Kế hoạch năm <ArrowRightOutlined />
    </Link>
  );
}

export default function DataLockPlanBlock({ plan, onOpenPlan }: Props) {
  const values = plan.values as Partial<YearPlanRow>;
  if (PLAN_FIELDS.every((f) => values[f.key] == null)) {
    return (
      <div style={{ marginTop: 14 }}>
        <div className="dlp-head">
          <h4 style={{ margin: 0 }}>Kế hoạch năm {plan.year}</h4>
          {onOpenPlan && <OpenPlanLink onOpen={onOpenPlan} />}
        </div>
        <div className="blt-error" style={{ fontSize: 12.5 }}>
          Chưa khai kế hoạch năm {plan.year} — nên nhập ở màn Kế hoạch năm trước khi chốt.
        </div>
      </div>
    );
  }

  const legacy = !(NEW_KEY in values);   // bản chụp trước khi có bộ chỉ tiêu mới
  const read = (r: (typeof PLAN_SECTIONS)[number]["rows"][number]) => {
    if (r.kind === "total") return totalInfo(values, PLAN_TOTALS[r.id]);
    const v = values[r.key];
    return { value: typeof v === "number" ? v : null, fromFallback: false };
  };

  const groups = PLAN_SECTIONS.map((s) => ({
    title: s.title,
    rows: s.rows
      .map((r) => ({ id: sectionRowId(r), total: r.kind === "total", ...read(r) }))
      .filter((r) => !legacy || r.value != null),
  })).filter((g) => g.rows.length > 0);

  const inputs = PLAN_SECTIONS.flatMap((s) => s.rows).filter((r) => r.kind === "field");
  const filled = inputs.filter((r) => read(r).value != null).length;
  const missing = inputs.length - filled;

  return (
    <div style={{ marginTop: 14 }}>
      <div className="dlp-head">
        <h4 style={{ margin: 0 }}>Kế hoạch năm {plan.year}</h4>
        <div className="dlp-right">
          {!legacy && (
            <span className={`dlp-chip ${missing ? "warn" : "ok"}`}>
              {missing ? `${filled}/${inputs.length} chỉ tiêu đã khai · còn ${missing} chưa khai` : `Đã khai đủ ${inputs.length} chỉ tiêu`}
            </span>
          )}
          {onOpenPlan && <OpenPlanLink onOpen={onOpenPlan} />}
        </div>
      </div>
      <div className="dlp">
        {groups.map((g) => (
          <div key={g.title} className="dlp-g">
            <div className="dlp-gh" title={SECTION_HINT[g.title]}>{g.title}</div>
            {g.rows.map((r) => {
              const ui = ROW_UI[r.id];
              return (
                <div key={r.id} className={`dlp-r${r.total ? " t" : ""}`}>
                  <span className="n">{ui.label}</span>
                  <span className="u">{ui.uom}</span>
                  <span className={`v${r.value == null ? " blank" : ""}`}>
                    {r.value == null ? "—" : n3(r.value)}
                    {r.fromFallback && <em title="Đơn vị chưa nhập mục con — đang hiện tổng đã khai từ trước"> số cũ</em>}
                  </span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
