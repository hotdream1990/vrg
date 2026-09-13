/* Chỉ số tài chính & tỷ giá trong kỳ: DXY · WTI · Brent (CNBC/Yahoo Finance, tự động — kèm link
   Investing.com để đối chiếu) + tỷ giá USD/JPY·CNY·MYR·THB của hệ thống (TB từng tuần). */

import { LinkOutlined, WarningOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";

import type { FxRow, WeekCol } from "../../../../lib/weekly-report-client";
import { type WeeklyIndicator, getWeeklyIndicators } from "../../../../lib/weekly-report-inputs-client";
import { autoDec, pairLabel, safeHref, signed, viDate, vn } from "./WeeklyFormat";

type Props = { weekKey: string; span: number; weeks: WeekCol[]; fxRows: FxRow[] };

/** Cách đọc chiều tỷ giá (Logic viết bản tin tuần: OSE ↔ Yên, SGX/MRE ↔ Baht/Ringgit). */
const FX_LOGIC: Record<string, string> = {
  "USD/JPY": "tăng = Yên yếu",
  "USD/CNY": "tăng = Nhân dân tệ yếu",
  "USD/MYR": "giảm = Ringgit mạnh lên",
  "USD/THB": "giảm = Baht mạnh lên",
};

type Row = {
  key: string; name: string; note?: string; url?: string | null; error?: string | null;
  values: (number | null)[]; changes: (number | null)[]; changes_pct: (number | null)[];
  high?: WeeklyIndicator["high"]; low?: WeeklyIndicator["low"];
};

export default function WeeklyIndicatorsCard({ weekKey, span, weeks, fxRows }: Props) {
  const [items, setItems] = useState<WeeklyIndicator[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true); setErr("");
    getWeeklyIndicators(weekKey, span)
      .then((r) => { if (alive) setItems(r.indicators ?? []); })
      .catch((e) => { if (alive) { setItems([]); setErr(e instanceof Error ? e.message : "Lỗi"); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [weekKey, span]);

  const shorts = weeks.map((w) => w.short || `T${w.week_no}`);
  const rows: Row[] = [
    ...items.map((it, i) => ({ ...it, key: `i${it.source_id ?? i}`, note: it.role ?? undefined })),
    ...(fxRows ?? []).map((f) => ({ ...f, key: `fx${f.pair}`, name: f.pair, note: FX_LOGIC[f.pair] })),
  ];
  const point = (p: WeeklyIndicator["high"]) =>
    p ? <>{vn(p.value, autoDec(p.value))}<div className="wk-muted">{viDate(p.date, true)}</div></> : "—";

  return (
    <div>
      {err && <div className="blt-error">Không lấy được chỉ số tài chính: {err}</div>}
      <div className="wk-scroll">
        <table className="wk-table wk-table-sm">
          <thead>
            <tr>
              <th>Chỉ số</th>
              {weeks.map((w, i) => <th key={w.mon} title={w.label}>TB {shorts[i]}</th>)}
              {weeks.slice(1).map((_, i) => <th key={i}>{pairLabel(shorts, i + 1)}</th>)}
              <th>Cao trong kỳ</th><th>Thấp trong kỳ</th><th>Đối chiếu</th>
            </tr>
          </thead>
          <tbody>
            {loading && !rows.length && (
              <tr><td colSpan={20} className="c wk-muted"><span className="spinner" /> Đang lấy số liệu…</td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.key}>
                <td>
                  <div className="wk-strong">{r.name}</div>
                  {r.note && <div className="wk-muted">{r.note}</div>}
                  {r.error && <div className="wk-ai-warn wk-inline"><WarningOutlined /> {r.error}</div>}
                </td>
                {weeks.map((w, i) => <td key={w.mon} className="r">{vn(r.values?.[i] ?? null, autoDec(r.values?.[i]))}</td>)}
                {weeks.slice(1).map((_, i) => (
                  <td key={i} className="r wk-chg">
                    {signed(r.changes?.[i] ?? null, autoDec(r.values?.[i + 1]))}
                    {r.changes_pct?.[i] != null && <div className="wk-muted">{signed(r.changes_pct[i], 2, "%")}</div>}
                  </td>
                ))}
                <td className="r">{r.high === undefined ? "—" : point(r.high)}</td>
                <td className="r">{r.low === undefined ? "—" : point(r.low)}</td>
                <td className="c">
                  {safeHref(r.url) ? (
                    <a href={safeHref(r.url) ?? undefined} target="_blank" rel="noopener noreferrer"><LinkOutlined /> Investing.com</a>
                  ) : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="wk-muted wk-source-line">
        Nguồn: chỉ số DXY · WTI · Brent lấy tự động từ CNBC (dự phòng Yahoo Finance) — bấm “Investing.com” để đối chiếu;
        tỷ giá lấy từ số liệu hệ thống. USD/JPY tăng = Yên yếu (hỗ trợ OSE) · USD/THB, USD/MYR giảm =
        Baht/Ringgit mạnh lên (nâng đỡ SGX/MRE).
      </div>
    </div>
  );
}
