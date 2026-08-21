import { Segmented } from "antd";
import { useEffect, useState } from "react";

import { dmy } from "../../../../lib/date";
import {
  type ConsumptionGroupBy, type ConsumptionSeries, fetchConsumptionSeries,
} from "../../../../lib/series-client";
import StackedDaysChart from "../../charts/StackedDaysChart";

const vnum = (n: number, d = 0) => n.toLocaleString("vi-VN", { maximumFractionDigits: d });
const WINDOW_DAYS = 30;
const TY = 1_000_000_000;

const VIEWS: { value: ConsumptionGroupBy; label: string }[] = [
  { value: "region", label: "Khu vực" },
  { value: "company", label: "Công ty" },
  { value: "grade", label: "Chủng loại" },
  { value: "contract", label: "Loại hợp đồng" },
  { value: "channel", label: "Hình thức" },
];

const SUBTITLE: Record<ConsumptionGroupBy, string> = {
  region: "Mỗi cột = sản lượng giao trong ngày chia theo khu vực — tấn",
  company: "Mỗi cột = sản lượng giao trong ngày chia theo công ty — tấn",
  grade: "Mỗi cột = sản lượng giao trong ngày chia theo chủng loại mủ — tấn",
  contract: "Mỗi cột = sản lượng giao trong ngày chia theo loại hợp đồng (dài hạn / chuyến) — tấn",
  channel: "Mỗi cột = sản lượng giao trong ngày chia theo hình thức (XK·UTXK / trong nước / nội bộ) — tấn",
};

const from = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() - (days - 1));
  return d.toISOString().slice(0, 10);
};

function caption(c: ConsumptionSeries): string {
  const last = c.rows.at(-1);
  if (!last) return "";
  const top = Object.entries(last.values).sort((a, b) => b[1] - a[1]).slice(0, 3)
    .map(([k, v]) => `${k} ${vnum(v)}`).join(", ");
  const tonnes = c.rows.reduce((t, r) => t + (r.total ?? 0), 0);
  return `Ngày ${dmy(last.as_of)}: ${vnum(last.total ?? 0)} tấn`
    + (last.revenue_vnd ? ` · ${vnum(last.revenue_vnd / TY, 1)} tỷ đồng` : "")
    + (top ? ` · nhiều nhất: ${top} tấn` : "")
    + `. Cả kỳ: ${vnum(tonnes)} tấn.`;
}

/** Tiêu thụ theo ngày — sản lượng giao (cột chồng) + doanh thu (đường, trục phải).
 *  Nguồn: các lần giao của hợp đồng bán hàng, cùng số với màn "Thống kê tiêu thụ". */
export default function ConsumptionBlock() {
  const [view, setView] = useState<ConsumptionGroupBy>("region");
  const [data, setData] = useState<ConsumptionSeries | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setData(null);
    fetchConsumptionSeries(view, from(WINDOW_DAYS))
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu"));
  }, [view]);

  const ready = !!data?.rows.length;
  const missing = data?.rows.reduce((t, r) => t + r.revenue_missing_lines, 0) ?? 0;

  return (
    <div className="card" id="sec-tieuthu">
      <div className="card-head">
        <div>
          <h3 className={ready ? undefined : "title-demo"}>
            Tiêu thụ theo ngày · {VIEWS.find((v) => v.value === view)!.label}
          </h3>
          <div className="sub">{data ? caption(data) : SUBTITLE[view]}</div>
        </div>
        <span className={`chip ${ready ? "" : "demo"}`}>{ready ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
        <Segmented size="small" value={view} options={VIEWS}
                   onChange={(v) => setView(v as ConsumptionGroupBy)} />
      </div>
      {err ? <div className="scan-empty">{err}</div>
        : !data ? <div className="scan-empty">Đang tải…</div>
        : !ready ? <div className="scan-empty">Chưa có lần giao hàng nào trong khoảng này.</div>
        : (
          <div className="chart-wrap">
            <StackedDaysChart
              rows={data.rows} series={data.series}
              extraLine={{
                label: "Doanh thu (tỷ đồng)", unit: "Tỷ đồng", color: "#0f766e",
                data: data.rows.map((r) => (r.revenue_vnd == null ? null : r.revenue_vnd / TY)),
              }}
              footer={(r) => {
                const row = r as ConsumptionSeries["rows"][number];
                return `Tổng ngày: ${vnum(row.total ?? 0)} tấn`
                  + (row.revenue_missing_lines
                    ? ` · ${row.revenue_missing_lines} dòng chưa có tỷ giá` : "");
              }}
            />
          </div>
        )}
      <p style={{ color: "var(--muted)", fontSize: 11, margin: "10px 0 0" }}>
        {SUBTITLE[view]}. Số liệu lấy từ các <b>lần giao của hợp đồng bán hàng</b> (đúng nguồn màn
        Thống kê tiêu thụ), tính theo ngày giao; đường doanh thu đọc theo trục phải.
        {missing > 0 && ` ${missing} dòng bán bằng USD chưa khai tỷ giá nên chưa vào doanh thu — sản lượng vẫn được tính.`}
      </p>
    </div>
  );
}
