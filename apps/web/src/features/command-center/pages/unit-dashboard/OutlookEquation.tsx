/* Dòng phương trình sản lượng CẢ PHẠM VI của card "Tiến độ bán hàng năm":
     Đã giao lũy kế + [HĐ chuyến đã ký chưa giao + HĐ dài hạn còn phải giao (+ HĐ chưa khai loại)]
     = Tổng bán cả năm (dự kiến).
   Nhóm giữa đóng khung = "Tổng phải giao đến cuối năm" (khác "Đã ký HĐ chưa giao" của tồn kho: phần
   dài hạn tính theo CAM KẾT HĐDH, gồm cả sản lượng chưa ký phụ lục). Số lấy nguyên từ server — web
   không tự cộng. Ô "HĐ chưa khai loại" chỉ hiện khi > 0. */

import { Fragment } from "react";

import { dmy } from "../../../../lib/date";
import type { OutlookBlock } from "../../../../lib/unit-dashboard-client";
import { fmtTon, fmtTons, isPositive } from "./dashboard-format";

type Tile = { label: string; value: number | null | undefined; sub: string; main?: boolean };

function EqTile({ label, value, sub, main }: Tile) {
  return (
    <div className={`ud-stat ud-eq-tile${main ? " is-main" : ""}`}>
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
  const b = data.backlog ?? {};
  const v = data.volume ?? {};
  const pending: Tile[] = [
    { label: "HĐ chuyến đã ký chưa giao", value: b.spot_undelivered, sub: "đã ký, chưa giao hết" },
    { label: "HĐ dài hạn còn phải giao", value: b.lt_remaining, sub: "HĐDH còn lại + HĐ dài hạn khác đã ký chưa giao" },
  ];
  if (isPositive(b.unknown_undelivered)) {
    pending.push({ label: "HĐ chưa khai loại", value: b.unknown_undelivered,
                   sub: "đã ký chưa giao, chưa khai chuyến / dài hạn" });
  }
  return (
    <div className="ud-eq">
      <EqTile label="Đã giao lũy kế" value={v.delivered_ytd} sub={`01/01 → ${dmy(data.as_of)}`} />
      <Op sign="+" />
      {/* flexGrow theo số ô bên trong: mọi ô của dòng rộng bằng nhau. */}
      <div className="ud-eq-group" style={{ flexGrow: pending.length }}>
        <div className="ud-eq-group-head">
          <span>Tổng phải giao đến cuối năm</span>
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
      <EqTile label="Tổng bán cả năm (dự kiến)" value={v.projected} sub="= đã giao + phải giao" main />
    </div>
  );
}
