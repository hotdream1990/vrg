/* Bảng nhỏ "Cao/Thấp trong kỳ" (range_stats) — để chuyên viên đối chiếu khi viết nhận định:
   giá USD/tấn + giá nội tệ (JPY/kg · CNY/tấn · US cent/kg) + ngày + tuần xảy ra. */

import type { RangeStat } from "../../../../lib/weekly-report-client";
import { nativeDec, vn } from "./WeeklyFormat";

type Props = { title: string; stats: RangeStat[]; withExchange: boolean };

function Point({ value, native, unit, date, week }: {
  value: number | null; native: number | null; unit: string | null; date: string | null; week: number | null;
}) {
  if (value === null || value === undefined) return <td className="c wk-muted">—</td>;
  return (
    <td className="r">
      <div className="wk-strong">{vn(value, 1)}</div>
      {native != null && unit && <div className="wk-muted">~{vn(native, nativeDec(unit))} {unit}</div>}
      <div className="wk-muted">{[date, week ? `T${week}` : ""].filter(Boolean).join(" · ")}</div>
    </td>
  );
}

export default function WeeklyRangeStats({ title, stats, withExchange }: Props) {
  if (!stats?.length) return null;
  return (
    <div className="wk-range">
      <div className="wk-subtle-title">{title}</div>
      <div className="wk-scroll">
        <table className="wk-table wk-table-sm">
          <thead>
            <tr>
              {withExchange && <th>Sàn</th>}<th>SP</th>
              <th>Cao nhất (USD/tấn)</th><th>Thấp nhất (USD/tấn)</th>
            </tr>
          </thead>
          <tbody>
            {stats.map((s) => (
              <tr key={`${s.exchange ?? ""}-${s.grade}`}>
                {withExchange && <td className="c">{s.exchange ?? ""}</td>}
                <td className="c">{s.grade}</td>
                <Point value={s.high} native={s.high_native} unit={s.native_unit}
                  date={s.high_date} week={s.high_week_no} />
                <Point value={s.low} native={s.low_native} unit={s.native_unit}
                  date={s.low_date} week={s.low_week_no} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
