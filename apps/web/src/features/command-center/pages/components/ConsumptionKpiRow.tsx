import {
  type BacklogTotals, type ConsumptionTotals, pct1, t3, ty, wet,
} from "./consumption-report-totals";

type Kpi = { label: string; value: string; sub?: string };

/** Phần PHẢI GIAO tách 3 thẻ theo yêu cầu khách (26/09/2026): HĐ chuyến đã ký chưa giao + HĐ dài hạn
 *  còn phải giao = tổng phải giao đến cuối năm; thêm 1 thẻ tiến độ HĐDH (HĐ nguyên tắc không tính).
 *  API cũ (chưa có `backlog`) → giữ 1 thẻ "Đã ký chưa giao" như trước. */
function backlogCards(totals: ConsumptionTotals, bl: BacklogTotals | null): Kpi[] {
  if (!bl) return [{ label: "Đã ký chưa giao (tấn quy khô)", value: t3(totals.remaining) }];
  return [
    { label: "HĐ chuyến đã ký chưa giao (tấn)", value: t3(bl.spot) },
    {
      label: "HĐ dài hạn còn phải giao (tấn)", value: t3(bl.lt),
      sub: "HĐDH còn lại (gồm phần chưa ký phụ lục) + HĐ dài hạn khác đã ký chưa giao",
    },
    {
      label: "Tổng phải giao đến cuối năm (tấn)", value: t3(bl.toDeliver),
      // Cùng cách tách với file Excel: HĐ chưa khai loại là một cột riêng, không gộp vào HĐ chuyến.
      sub: bl.unknown > 0 ? `Gồm ${t3(bl.unknown)} tấn HĐ chưa khai loại` : undefined,
    },
    {
      label: "Tiến độ HĐ dài hạn (HĐDH)", value: pct1(bl.pct),
      sub: bl.committed > 0
        ? `Đã giao ${t3(bl.delivered)} / cam kết ${t3(bl.committed)} tấn (lũy kế từ ngày ký) · còn phải giao ${t3(bl.masterRemaining)}`
        : "Chưa có HĐDH nào có sản lượng cam kết",
    },
  ];
}

export default function ConsumptionKpiRow(
  { totals, backlog }: { totals: ConsumptionTotals; backlog: BacklogTotals | null },
) {
  const cards: Kpi[] = [
    { label: "Sản lượng tiêu thụ (tấn quy khô)", value: t3(totals.qty) },
    { label: "Trong đó: SL chưa quy khô (tấn)", value: wet(totals.qty_wet) },
    { label: "Doanh thu (tỷ đồng)", value: ty(totals.revenue) },
    { label: "Số lần giao", value: totals.deliveries.toLocaleString("vi-VN") },
    ...backlogCards(totals, backlog),
  ];
  return (
    <div className="kpi-row">
      {cards.map((k) => (
        <div className="kpi" key={k.label}>
          <div className="label">{k.label}</div>
          <div className="value">{k.value}</div>
          {k.sub && <div className="sub">{k.sub}</div>}
        </div>
      ))}
    </div>
  );
}
