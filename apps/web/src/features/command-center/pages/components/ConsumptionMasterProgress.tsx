import { DownOutlined, RightOutlined } from "@ant-design/icons";
import { Fragment, useState } from "react";

import { dmy } from "../../../../lib/date";
import type { ConsumptionReport } from "../../../../lib/sales-contract-client";
import ConsumptionMasterItems, { PctBar } from "./ConsumptionMasterItems";
import { type BacklogTotals, t3 } from "./consumption-report-totals";
import "./consumption-master-progress.css";

type Props = { rep: ConsumptionReport; totals: BacklogTotals | null };

/** "HĐ dài hạn đã giao bao nhiêu trên số đã ký từ HĐ mẹ, còn lại bao nhiêu, tỷ lệ thực hiện" (yêu cầu
 *  khách 26/09/2026). Mỗi đơn vị một dòng, bấm để xem từng HĐDH (HĐ nguyên tắc không tính — 28/09/2026).
 *  Chỉ hiện khi có đơn vị có HĐDH
 *  mang sản lượng cam kết; API cũ (chưa có `backlog`) → không hiện gì. */
export default function ConsumptionMasterProgress({ rep, totals }: Props) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const backlog = rep.backlog ?? {};
  const units = Object.keys(backlog).filter((c) => backlog[c].masters > 0).sort();
  if (!totals || !units.length) return null;

  const showExpired = units.some((c) => backlog[c].master_expired_short > 0);
  const cols = showExpired ? 7 : 6;
  const toggle = (c: string) => setOpen((s) => {
    const next = new Set(s);
    if (next.has(c)) next.delete(c); else next.add(c);
    return next;
  });

  return (
    <>
      <div className="blt-toolbar" style={{ marginTop: 14 }}>
        <b>Tiến độ hợp đồng dài hạn (HĐDH)</b>
        <span style={{ color: "var(--muted)", fontSize: 13 }}>
          tính đến {dmy(rep.backlog_as_of ?? rep.date_to)} · bấm một dòng để xem từng HĐDH
        </span>
      </div>
      <div className="card cmp-card">
        <table>
          <thead><tr>
            <th>Đơn vị</th><th className="r">Số HĐDH</th>
            <th className="r">Cam kết (tấn)</th><th className="r">Đã giao (tấn)</th>
            <th className="r">Còn phải giao (tấn)</th><th className="r">% thực hiện</th>
            {showExpired && <th className="r">Hết hạn chưa giao đủ (tấn)</th>}
          </tr></thead>
          <tbody>
            {units.map((c) => {
              const b = backlog[c];
              const isOpen = open.has(c);
              return (
                <Fragment key={c}>
                  <tr className="row-drill" aria-expanded={isOpen} onClick={() => toggle(c)}>
                    <td style={{ fontWeight: 500 }}>
                      {isOpen ? <DownOutlined className="cmp-caret" /> : <RightOutlined className="cmp-caret" />}
                      {c}
                    </td>
                    <td className="r">{b.masters.toLocaleString("vi-VN")}</td>
                    <td className="r">{t3(b.master_committed)}</td>
                    <td className="r">{t3(b.master_delivered)}</td>
                    <td className="r" style={{ fontWeight: 600 }}>{t3(b.master_remaining)}</td>
                    <td className="r"><PctBar pct={b.master_pct} /></td>
                    {showExpired && (
                      <td className="r">{b.master_expired_short > 0 ? t3(b.master_expired_short) : "—"}</td>
                    )}
                  </tr>
                  {isOpen && (
                    <tr>
                      <td colSpan={cols} className="cmp-items-cell">
                        <ConsumptionMasterItems items={b.items ?? []} customers={rep.customers ?? {}} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
          <tfoot>
            <tr style={{ fontWeight: 600 }}>
              <td>Tổng · {units.length} đơn vị</td>
              <td className="r">{totals.masters.toLocaleString("vi-VN")}</td>
              <td className="r">{t3(totals.committed)}</td>
              <td className="r">{t3(totals.delivered)}</td>
              <td className="r">{t3(totals.masterRemaining)}</td>
              <td className="r"><PctBar pct={totals.pct} /></td>
              {showExpired && <td className="r">{t3(totals.expiredShort)}</td>}
            </tr>
          </tfoot>
        </table>
      </div>
      <div className="cmp-note">
        Đã giao tính lũy kế từ ngày ký HĐDH. Còn phải giao của một HĐDH = cam kết − đã giao (không
        thấp hơn phần phụ lục đã ký chưa giao); HĐDH đã hết hạn chỉ còn phần phụ lục đã ký chưa giao —
        cam kết chưa ký phụ lục của nó ghi ở cột “Hết hạn chưa giao đủ”. HĐ nguyên tắc không tính ở đây:
        sản lượng ghi trên đó chỉ là dự kiến, phụ lục của nó tính theo loại của chính phụ lục.
      </div>
    </>
  );
}
