/* Bảng thống kê dùng chung: cột động + dòng Tổng cộng lấy THẲNG từ server
   (giá bình quân phải tính gia quyền trên toàn bộ dữ liệu — cộng ở client sẽ ra số sai). */

import { Alert, Spin } from "antd";

import { dmy } from "../../../../lib/date";
import type { StatsRow } from "../../../../lib/unit-analytics-client";
import { displayDigits, fmtNum } from "../../../../lib/unit-daily-fields";

export type StatsCol = {
  key: string;
  label: string;
  unit?: string;
  note?: string;
  text?: boolean;      // cột chữ (số HĐ, chủng loại…) — không định dạng số
  date?: boolean;      // cột ngày — hiển thị DD/MM/YYYY
};

type Props = {
  // Tiêu đề cột nhóm ("Đơn vị" / "Khu vực" / "Chủng loại" / "Ngày").
  // Rỗng = bảng CHI TIẾT từng dòng → không có cột nhóm (mỗi dòng tự đủ thông tin).
  groupLabel: string;
  cols: StatsCol[];
  rows: StatsRow[];
  totals?: StatsRow | null;
  showRegion?: boolean;        // hiện cột Khu vực (chỉ khi nhóm theo đơn vị)
  loading?: boolean;
  warnings?: string[];
  empty?: string;
};

const cell = (row: StatsRow, c: StatsCol) => {
  const v = row[c.key];
  if (c.date) return dmy(v as string | null);
  if (c.text) return (v as string) || "—";
  return fmtNum(typeof v === "number" ? v : null, displayDigits(c.unit ?? ""));
};

export default function StatsTable({
  groupLabel, cols, rows, totals, showRegion, loading, warnings, empty,
}: Props) {
  const hasGroupCol = !!groupLabel;
  const lead = (showRegion ? 1 : 0) + (hasGroupCol ? 1 : 0);
  return (
    <>
      {(warnings ?? []).map((w) => (
        <Alert key={w} type="warning" showIcon title={w} style={{ marginBottom: 10 }} />
      ))}
      <Spin spinning={!!loading}>
        <div className="card" style={{ padding: 0, overflow: "auto" }}>
          <table>
            <thead>
              <tr>
                {showRegion && <th style={{ minWidth: 120 }}>Khu vực</th>}
                {hasGroupCol && <th style={{ minWidth: 170 }}>{groupLabel}</th>}
                {cols.map((c) => (
                  <th key={c.key} className="r" style={{ minWidth: 118 }}>
                    {c.label}
                    {c.unit && <div style={{ fontWeight: 400, fontSize: 10.5, opacity: 0.6 }}>{c.unit}</div>}
                    {c.note && (
                      <div style={{ fontWeight: 400, fontSize: 10, opacity: 0.45, fontStyle: "italic" }}>
                        {c.note}
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.key ?? i}`}>
                  {showRegion && <td>{r.region ?? "—"}</td>}
                  {hasGroupCol && <td style={{ fontWeight: 500 }}>{r.label ?? r.key ?? "—"}</td>}
                  {cols.map((c) => (
                    <td key={c.key} className="r">{cell(r, c)}</td>
                  ))}
                </tr>
              ))}
              {!rows.length && !loading && (
                <tr>
                  <td colSpan={cols.length + lead}
                      style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                    {empty ?? "Không có số liệu khớp bộ lọc."}
                  </td>
                </tr>
              )}
              {!!rows.length && totals && (
                <tr style={{ fontWeight: 600, background: "rgba(125,125,125,.08)" }}>
                  {showRegion && <td />}
                  <td>Tổng cộng</td>
                  {cols.map((c) => (
                    <td key={c.key} className="r">{c.text ? "" : cell(totals, c)}</td>
                  ))}
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Spin>
    </>
  );
}
