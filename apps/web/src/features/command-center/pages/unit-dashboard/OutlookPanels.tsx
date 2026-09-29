/* 3 khối dưới dòng phương trình của card "Tiến độ bán hàng năm": HĐ dài hạn (HĐDH) · So KH bán
   hàng (khai thác + thu mua) · Doanh thu dự kiến.
   % so KH tính trên RỔ đơn vị có KH — khác số cả phạm vi ở dòng phương trình → luôn ghi rõ rổ, lệch
   đáng kể thì nêu kèm số cả phạm vi (phản hồi 26/09/2026). Có KH mà không ra % = vướng DỮ LIỆU
   (thiếu tỷ giá, đơn giá sai đơn vị tính…) → `note` server tô cảnh báo. */

import type { ReactNode } from "react";

import type { OutlookBlock } from "../../../../lib/unit-dashboard-client";
import { differsNotably, fmtTon, fmtTons, fmtTy, isPositive } from "./dashboard-format";
import { MiniEquation, PctProgress } from "./OutlookBars";

type Num = number | null | undefined;
type Props = { data: OutlookBlock; single: boolean };

const count = (v: Num) => (v ?? 0).toLocaleString("vi-VN");

/** Nhãn rổ "N đơn vị có KH" — xem 1 đơn vị hoặc API chưa gửi số thì bỏ (không ghi "0 đơn vị"). */
const basketTag = (single: boolean, n: Num) => (single || n == null ? undefined : `${count(n)} đơn vị có KH`);

/** Cả phương trình đều "—" = API chưa gửi khoá → ẩn, khỏi một dòng toàn gạch. */
const anyNum = (...vals: Num[]) => vals.some((x) => x != null);

function Panel({ title, tag, children }: { title: string; tag?: string; children: ReactNode }) {
  return (
    <div className="ud-ol-panel">
      <div className="ud-target-head">
        <b>{title}</b>
        {tag && <span className="ud-target-nums">{tag}</span>}
      </div>
      {children}
    </div>
  );
}

/** Thanh % so KH · hoặc lý do chưa ra % · kèm `note` server (muted khi đã có %). */
function PlanProgress({ plan, pct, note, noPlan }: { plan: Num; pct: Num; note?: string; noPlan: string }) {
  if (!isPositive(plan)) return <div className="ud-muted ud-small">{noPlan}</div>;
  if (pct == null) return <div className="ud-warn ud-small">{note || "Chưa tính được % so kế hoạch."}</div>;
  return (
    <>
      <PctProgress pct={pct} />
      {note && <div className="ud-muted ud-small">{note}</div>}
    </>
  );
}

function LtPanel({ data }: { data: OutlookBlock }) {
  const lt = data.lt ?? {};
  const has = isPositive(lt.committed);
  return (
    <Panel title="HĐ dài hạn (HĐDH)" tag={has ? `${count(lt.masters)} HĐDH có cam kết` : undefined}>
      {!has ? (
        <div className="ud-muted ud-small">
          Chưa có HĐDH nào có cam kết sản lượng hiệu lực trong năm {data.year}.
        </div>
      ) : (
        <>
          <div className="ud-ol-figure">
            Đã giao <b>{fmtTon(lt.delivered)}</b> / cam kết <b>{fmtTon(lt.committed)}</b> tấn
          </div>
          <div className="ud-muted ud-small">Lũy kế từ ngày ký HĐDH (gồm cả phần giao năm trước).</div>
          {lt.pct == null
            ? <div className="ud-muted ud-small">Chưa tính được tỷ lệ thực hiện.</div>
            : <PctProgress pct={lt.pct} />}
          <div className="ud-ol-figure">Còn phải giao theo HĐDH <b>{fmtTons(lt.remaining)}</b></div>
        </>
      )}
      {isPositive(lt.remaining_after_year) && (
        <div className="ud-muted ud-small">
          Trong đó {fmtTons(lt.remaining_after_year)} thuộc HĐDH còn hiệu lực sau 31/12/{data.year}
          hoặc không thời hạn — chưa chắc giao hết trong năm.
        </div>
      )}
      {isPositive(lt.expired_short) && (
        <div className="ud-muted ud-small">
          HĐDH đã hết hạn: {fmtTons(lt.expired_short)} cam kết chưa ký phụ lục không còn phải giao
          (phụ lục đã ký vẫn tính).
        </div>
      )}
      {isPositive(lt.unlinked_undelivered) && (
        <div className="ud-muted ud-small">
          “HĐ dài hạn còn phải giao” gồm thêm {fmtTons(lt.unlinked_undelivered)} HĐ dài hạn khác
          đã ký chưa giao (ngoài HĐDH có cam kết, kể cả phụ lục của HĐ nguyên tắc).
        </div>
      )}
    </Panel>
  );
}

function VolumePanel({ data, single }: Props) {
  const v = data.volume ?? {};
  const missing = v.units_missing_exploit ?? 0;
  return (
    <Panel title="So kế hoạch bán hàng" tag={basketTag(single, v.units_planned)}>
      <div className="ud-ol-figure">
        Bán cả năm (dự kiến) <b>{fmtTon(single ? v.projected : v.basket_projected)}</b> / KH <b>{fmtTon(v.plan_total)}</b> tấn
      </div>
      <PlanProgress
        plan={v.plan_total} pct={v.pct} note={v.note}
        noPlan={single ? `Chưa có KH bán hàng năm ${data.year} (khai thác + thu mua + hàng hóa).`
          : "Chưa đơn vị nào đủ KH khai thác + thu mua để so."}
      />
      {anyNum(v.plan_exploit, v.plan_purchase, v.plan_total) && (
        <MiniEquation unit="tấn" terms={[
          { label: "KH khai thác", value: fmtTon(v.plan_exploit) },
          { label: "KH thu mua", value: fmtTon(v.plan_purchase) },
          // Hàng hóa = thành phẩm mua ngoài bán lại — sản lượng bán có phần này nên KH cũng phải có.
          { label: "KH hàng hóa", value: fmtTon(v.plan_goods) },
          { label: "KH bán hàng", value: fmtTon(v.plan_total) },
        ]} />
      )}
      {!single && isPositive(v.units_planned) && (
        <div className="ud-muted ud-small">
          Tính trên {count(v.units_planned)} đơn vị đã nhập KH khai thác
          {differsNotably(v.basket_projected, v.projected)
            && ` · cả phạm vi dự kiến bán ${fmtTons(v.projected)} (gồm đơn vị ngoài rổ)`}.
        </div>
      )}
      {missing > 0 && (
        <div className="ud-warn ud-small">
          {single ? "Đơn vị" : `${count(missing)} đơn vị`} chưa nhập KH khai thác năm {data.year} (màn
          Kế hoạch năm) — chưa đưa vào %.
        </div>
      )}
    </Panel>
  );
}

function RevenuePanel({ data, single }: Props) {
  const r = data.revenue ?? {};
  return (
    <Panel title="Doanh thu dự kiến" tag={basketTag(single, r.units_planned)}>
      <div className="ud-ol-figure">
        {single ? "Dự kiến" : "Rổ có KH: dự kiến"} <b>{fmtTy(single ? r.projected : r.basket_projected)}</b>
        {" "}/ KH <b>{fmtTy(r.plan)}</b> tỷ đ
      </div>
      <PlanProgress
        plan={r.plan} pct={r.pct} note={r.note}
        noPlan={single ? `Chưa giao KH doanh thu năm ${data.year}.` : "Chưa đơn vị nào được giao KH doanh thu."}
      />
      {anyNum(r.done_ytd, r.expected_rest, r.projected) && (
        <MiniEquation unit="tỷ đ" lead={single ? undefined : "Cả phạm vi"} terms={[
          { label: "Đã thực hiện", value: fmtTy(r.done_ytd) },
          { label: "Dự kiến phần còn lại", value: fmtTy(r.expected_rest) },
          { label: "Tổng dự kiến", value: fmtTy(r.projected) },
        ]} />
      )}
    </Panel>
  );
}

export default function OutlookPanels({ data, single }: Props) {
  return (
    <div className="ud-ol-panels">
      <LtPanel data={data} />
      <VolumePanel data={data} single={single} />
      <RevenuePanel data={data} single={single} />
    </div>
  );
}
