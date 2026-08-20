/* Dòng LŨY KẾ cuối bảng báo cáo theo ngày — hai biểu lấy số từ hai nguồn khác nhau:

   - Thu mua: web có TRỌN khoảng (bảng không cắt trang) nên tự cộng lấy (`timelineTotals`).
   - Tiêu thụ – Tồn kho: bảng cắt trang ở server → SERVER cộng cả khoảng và trả về `totals`,
     web chỉ in ra. Tồn kho là chỉ tiêu THỜI ĐIỂM nên server lấy ảnh chụp MỚI NHẤT của từng đơn vị
     (không cộng dồn qua các ngày) — ngày của ảnh chụp ghi ngay cạnh nhãn để không ai đọc nhầm. */

import { Table } from "antd";

import { dmy } from "../../../lib/date";
import type { TimelineRow, TimelineTotals } from "../../../lib/unit-daily-client";
import { COLUMNS, type Kind, displayDigits, fmtNum } from "../../../lib/unit-daily-fields";
import { timelineTotals } from "../../../lib/unit-daily-totals";

const GREEN = "#0a9e48";

type Props = { kind: Kind; rows: TimelineRow[]; totals?: TimelineTotals; extraCols: number };

export default function UnitDailyTimelineSummary({ kind, rows, totals, extraCols }: Props) {
  if (rows.length === 0) return null;
  const cols = COLUMNS[kind];
  const own = kind === "purchase" ? timelineTotals(kind, rows) : null;
  if (!own && !totals) return null;   // biểu tiêu thụ mà server chưa trả tổng thì thà không hiện

  return (
    <Table.Summary fixed>
      {/* Nền của dòng nằm ở CSS (`.ant-table-summary > tr > td`) chứ không đặt inline: ô phải có
          nền ĐỤC mới ghim đáy được, nền trong suốt thì các dòng chạy xuyên qua. */}
      <Table.Summary.Row>
        <Table.Summary.Cell index={0} colSpan={2}>
          <b style={{ color: GREEN }}>Lũy kế (khoảng đang xem)</b>
          {!own && (
            <div style={{ fontWeight: 400, color: "var(--muted)", fontSize: 11, lineHeight: 1.35 }}>
              {totals?.stock_as_of
                ? `tồn kho: số mới nhất ${dmy(totals.stock_as_of)}`
                : "tồn kho: chưa đơn vị nào chốt số trong khoảng"}
              {/* Tiêu thụ là DÒNG CHẢY (cộng dồn) còn tồn kho là số THỜI ĐIỂM — nói rõ nguồn để
                  không ai tưởng hai nhóm cột cùng một cách tính. */}
              <br />tiêu thụ: cộng dồn các lần giao trên hợp đồng
            </div>
          )}
        </Table.Summary.Cell>
        {cols.map((c, i) => {
          const t = own?.[c.key];
          const value = own ? t?.display ?? null : totals?.[c.key] ?? null;
          const blank = own ? t?.mode === "none" : false;
          return (
            <Table.Summary.Cell key={c.key} index={2 + i} align="right">
              {blank ? null : (
                <b>
                  {fmtNum(value, displayDigits(c.unit))}
                  {t?.mode === "avg" && value != null && (
                    <span style={{ fontWeight: 400, opacity: 0.55, fontSize: 11 }}> BQ</span>
                  )}
                </b>
              )}
            </Table.Summary.Cell>
          );
        })}
        {Array.from({ length: extraCols }, (_, i) => (
          <Table.Summary.Cell key={`x${i}`} index={2 + cols.length + i} />
        ))}
      </Table.Summary.Row>
    </Table.Summary>
  );
}
