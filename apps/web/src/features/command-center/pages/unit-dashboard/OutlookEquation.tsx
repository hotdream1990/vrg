/* Dòng phương trình sản lượng CẢ PHẠM VI của card "Tiến độ bán hàng năm":
     Đã giao lũy kế + [HĐ chuyến + HĐNT đã ký chưa giao + HĐ dài hạn còn phải giao (+ HĐ chưa khai loại)]
     = Tổng sản lượng sau khi giao hết.
   Nhóm giữa đóng khung = "Tổng còn phải giao" (khác "Đã ký HĐ chưa giao" của tồn kho: phần
   dài hạn tính theo CAM KẾT HĐDH, gồm cả sản lượng chưa ký phụ lục). Số lấy nguyên từ server — web
   không tự cộng. Ba nhóm chuyến · HĐNT · dài hạn luôn hiện (kể cả = 0); ô "HĐ chưa khai loại" chỉ hiện
   khi > 0. */

import { Fragment } from "react";

import { dmy } from "../../../../lib/date";
import type { OutlookBlock } from "../../../../lib/unit-dashboard-client";
import { fmtTon, fmtTons, isPositive } from "./dashboard-format";

type Tile = { label: string; value: number | null | undefined; sub: string; main?: boolean; critical?: boolean };

function EqTile({ label, value, sub, main, critical }: Tile) {
  return (
    <div className={`ud-stat ud-eq-tile${main ? " is-main" : ""}${critical ? " is-critical" : ""}`}>
      <div className="ud-stat-label">{label}</div>
      <div className="ud-stat-value">
        {fmtTon(value)}{value != null && <small> tấn</small>}
      </div>
      <div className="ud-stat-sub">{sub}</div>
    </div>
  );
}

const Op = ({ sign }: { sign: "+" | "=" }) => <span className="ud-eq-op ud-eq-op-lg" aria-hidden>{sign}</span>;

export default function OutlookEquation({ data }: { data: OutlookBlock }) {
  const lt = data.lt ?? {};
  const b = data.backlog ?? {};
  const v = data.volume ?? {};
  const otherLongTerm = (b.lt_remaining ?? 0) - (lt.remaining ?? 0) - (lt.missing_master_undelivered ?? 0);
  const pending: Tile[] = [
    { label: "HĐ chuyến đã ký chưa giao", value: b.spot_undelivered, sub: "đã ký, chưa giao hết" },
    { label: "HĐNT đã ký chưa giao", value: b.principle_undelivered, sub: "phụ lục HĐNT đã ký, chưa giao hết" },
    { label: "Còn phải giao theo cam kết HĐDH", value: lt.remaining, sub: "cam kết HĐDH trừ phần đã giao" },
  ];
  if (isPositive(lt.missing_master_undelivered)) {
    pending.push({ label: "HĐ dài hạn chưa gán HĐ mẹ", value: lt.missing_master_undelivered,
                   sub: "lỗi dữ liệu — cần gán HĐ mẹ", critical: true });
  }
  if (otherLongTerm > 1e-9) {
    pending.push({ label: "HĐ dài hạn ngoài cam kết HĐDH", value: otherLongTerm,
                   sub: "đã có HĐ mẹ nhưng không thuộc cam kết HĐDH đang tính" });
  }
  if (isPositive(b.unknown_undelivered)) {
    pending.push({ label: "HĐ chưa khai loại", value: b.unknown_undelivered,
                   sub: "đã ký chưa giao, chưa khai loại hợp đồng" });
  }
  return (
    <div className="ud-eq">
      <EqTile label="Đã giao lũy kế" value={v.delivered_ytd} sub={`01/01 → ${dmy(data.as_of)}`} />
      <Op sign="+" />
      {/* flexGrow theo số ô bên trong: mọi ô của dòng rộng bằng nhau. */}
      <div className="ud-eq-group" style={{ flexGrow: pending.length }}>
        <div className="ud-eq-group-head">
          <span>Tổng còn phải giao theo hợp đồng</span>
          <b>{fmtTons(b.to_deliver)}</b>
        </div>
        <div className="ud-eq-group-body">
          {pending.map((t, i) => (
            <Fragment key={t.label}>
              {i > 0 && <Op sign="+" />}
              <EqTile {...t} />
            </Fragment>
          ))}
        </div>
      </div>
      <Op sign="=" />
      <EqTile label="Tổng sản lượng sau khi giao hết" value={v.projected} sub="= đã giao + toàn bộ còn phải giao" main />
    </div>
  );
}
