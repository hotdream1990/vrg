/* Bảng CÂY hai cấp của màn Chỉ số đơn vị: TOÀN TẬP ĐOÀN → khu vực (mở/gập) → đơn vị.

   Mọi con số lấy THẲNG từ server, kể cả dòng khu vực và dòng tổng: giá bình quân phải tính gia
   quyền và `% KH = Σ thực hiện ÷ Σ kế hoạch` — cộng lại ở web là ra số sai.
   Ô trống nghĩa là CHƯA CÓ SỐ, không phải 0; đơn vị chưa có số vẫn giữ dòng để nhìn ra ai còn thiếu. */

import { DownOutlined, RightOutlined } from "@ant-design/icons";
import { Alert, Spin, Tooltip } from "antd";
import { useState } from "react";

import { dmy } from "../../../../lib/date";
import { displayDigits, fmtNum } from "../../../../lib/unit-daily-fields";
import type {
  ScorecardCol, ScorecardRegion, ScorecardValues,
} from "../../../../lib/unit-scorecard-client";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Một ô số: cột có đơn vị tính → số; cột ngày → DD/MM/YYYY; chưa có số → gạch ngang. */
function cell(values: ScorecardValues, c: ScorecardCol) {
  const v = values[c.key];
  if (v === null || v === undefined) return <span className="sc-empty">—</span>;
  if (typeof v === "string") return ISO_DATE.test(v) ? dmy(v) : v;
  return fmtNum(v, displayDigits(c.unit));
}

type Props = {
  cols: ScorecardCol[];
  regions: ScorecardRegion[];
  totals: ScorecardValues;
  loading?: boolean;
  warnings?: string[];
  hideEmptyUnits: boolean;
  empty?: string;
};

export default function ScorecardTable({
  cols, regions, totals, loading, warnings, hideEmptyUnits, empty,
}: Props) {
  const [closed, setClosed] = useState<Record<string, boolean>>({});
  const toggle = (r: string) => setClosed((s) => ({ ...s, [r]: !s[r] }));
  const nothing = !regions.length;

  return (
    <>
      {(warnings ?? []).map((w) => (
        <Alert key={w} type="warning" showIcon message={w} style={{ marginBottom: 10 }} />
      ))}
      <Spin spinning={!!loading}>
        <div className="card sc-wrap">
          <table className="sc-table">
            <thead>
              <tr>
                <th className="sc-name">Đơn vị / Khu vực</th>
                {cols.map((c) => (
                  <th key={c.key} className="r">
                    {c.label}
                    <div className="sc-sub">
                      {c.unit && <span>{c.unit}</span>}
                      {c.note && <span className="sc-note"> · {c.note}</span>}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr className="sc-total">
                <td className="sc-name">TOÀN TẬP ĐOÀN</td>
                {cols.map((c) => <td key={c.key} className="r">{cell(totals, c)}</td>)}
              </tr>
              {regions.map((g) => {
                const open = !closed[g.region];
                const units = hideEmptyUnits ? g.children.filter((u) => u.has_data) : g.children;
                return [
                  <tr key={g.region} className="sc-region" onClick={() => toggle(g.region)}>
                    <td className="sc-name">
                      {open ? <DownOutlined /> : <RightOutlined />}
                      <b style={{ marginLeft: 6 }}>{g.region}</b>
                      <span className="sc-count">
                        {g.units} đv
                        {g.no_data > 0 && (
                          <Tooltip title="Đơn vị chưa có số liệu nào ở tab này — ô để trống, không tính là 0.">
                            <span className="sc-warn"> · {g.no_data} chưa có số</span>
                          </Tooltip>
                        )}
                      </span>
                    </td>
                    {cols.map((c) => <td key={c.key} className="r">{cell(g.values, c)}</td>)}
                  </tr>,
                  ...(open ? units.map((u) => (
                    <tr key={`${g.region}/${u.company}`} className={u.has_data ? "" : "sc-dim"}>
                      <td className="sc-name sc-unit">
                        {u.company}
                        {u.merged_into && (
                          <span className="sc-count"> · đã sáp nhập vào {u.merged_into}</span>
                        )}
                      </td>
                      {cols.map((c) => <td key={c.key} className="r">{cell(u.values, c)}</td>)}
                    </tr>
                  )) : []),
                ];
              })}
              {nothing && (
                <tr>
                  <td className="sc-name" colSpan={cols.length + 1} style={{ textAlign: "center" }}>
                    {empty ?? "Không có dữ liệu theo bộ lọc hiện tại."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Spin>
    </>
  );
}
