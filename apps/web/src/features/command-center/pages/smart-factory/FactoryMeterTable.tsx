/* Bảng chỉ số theo ngày: mỗi chỉ số một nhóm cột (Chỉ số đầu · Chỉ số cuối · Tiêu thụ) + định mức
   theo bành. Giờ đọc số chỉ ghi ra khi KHÔNG phải mốc 00:00 (mẫu bù trong ngày / hôm nay).
   Dòng tổng lấy thẳng `summary` + `intensity` server trả — web không tự cộng lại. */

import {
  ClockCircleOutlined, ExclamationCircleOutlined, MinusCircleOutlined, WarningOutlined,
} from "@ant-design/icons";
import { Table, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Fragment, type ReactNode } from "react";

import { dmy } from "../../../../lib/date";
import type {
  DailyMeters, DailyRow, MeterCell, MeterFlag, MetricKey, MetricMeta,
} from "../../../../lib/smart-factory-client";
import {
  flagText, fmtNum, fmtReading, fmtUsed, hhmm, isMidnight, stampLocal, upperFirst, usedWord,
} from "./smart-factory-format";

const FLAG_ICON: Record<NonNullable<MeterFlag>, ReactNode> = {
  partial: <WarningOutlined className="sf-flag-partial" />,
  reset: <ExclamationCircleOutlined className="sf-flag-reset" />,
  no_data: <MinusCircleOutlined className="sf-flag-no_data" />,
  in_progress: <ClockCircleOutlined className="sf-flag-in_progress" />,
};

function Reading({ cell, side, k }: { cell?: MeterCell; side: "open" | "close"; k: MetricKey }) {
  const v = cell?.[side] ?? null;
  const at = (side === "open" ? cell?.open_at : cell?.close_at) ?? null;
  return (
    <>
      {fmtReading(v, k)}
      {v != null && !isMidnight(at) && (
        <Tooltip title={`Số đọc lúc ${stampLocal(at)}`}>
          <span className="sf-at">lúc {hhmm(at)}</span>
        </Tooltip>
      )}
    </>
  );
}

function Used({ cell, k }: { cell?: MeterCell; k: MetricKey }) {
  const note = flagText(cell);
  return (
    <span className="sf-used">
      {note && cell?.flag && <Tooltip title={note}>{FLAG_ICON[cell.flag]}</Tooltip>}
      {fmtUsed(cell?.used, k)}
    </span>
  );
}

const metricGroup = (m: MetricMeta) => ({
  title: `${m.label} (${m.unit})`,
  key: m.key,
  children: [
    { title: "Chỉ số đầu", key: `${m.key}-open`, align: "right" as const,
      render: (_: unknown, r: DailyRow) => <Reading cell={r[m.key]} side="open" k={m.key} /> },
    { title: "Chỉ số cuối", key: `${m.key}-close`, align: "right" as const,
      render: (_: unknown, r: DailyRow) => <Reading cell={r[m.key]} side="close" k={m.key} /> },
    { title: upperFirst(usedWord(m.key)), key: `${m.key}-used`, align: "right" as const,
      render: (_: unknown, r: DailyRow) => <Used cell={r[m.key]} k={m.key} /> },
  ],
});

type RatioCol = { key: "kwh_per_bale" | "m3_per_bale"; title: string; digits: number };

/** Cột định mức chỉ có khi nhà máy khai cả số bành lẫn điện (nước). */
function ratioCols(data: DailyMeters): RatioCol[] {
  const has = (k: MetricKey) => data.metrics.some((m) => m.key === k);
  if (!has("bales")) return [];
  return [
    has("energy") && { key: "kwh_per_bale" as const, title: "kWh/bành", digits: 2 },
    has("water") && { key: "m3_per_bale" as const, title: "m³/bành", digits: 3 },
  ].filter((c): c is RatioCol => !!c);
}

const isToday = (r: DailyRow, metrics: MetricMeta[]) =>
  metrics.some((m) => r[m.key]?.flag === "in_progress");

export default function FactoryMeterTable({ data }: { data: DailyMeters }) {
  const ratios = ratioCols(data);
  const columns: ColumnsType<DailyRow> = [
    { title: "Ngày", dataIndex: "date", key: "date", fixed: "left", render: (d: string) => dmy(d) },
    ...data.metrics.map(metricGroup),
    ...ratios.map((c) => ({
      title: c.title, key: c.key, align: "right" as const,
      render: (_: unknown, r: DailyRow) => fmtNum(r[c.key], c.digits),
    })),
  ];
  const ratioStart = 1 + data.metrics.length * 3;

  const summaryRow = (label: string, pick: "total" | "avg_per_day") => (
    <Table.Summary.Row className="sf-summary">
      <Table.Summary.Cell index={0}>{label}</Table.Summary.Cell>
      {data.metrics.map((m, i) => (
        <Fragment key={m.key}>
          <Table.Summary.Cell index={1 + i * 3} colSpan={2} />
          <Table.Summary.Cell index={3 + i * 3} align="right">
            {fmtUsed(data.summary[m.key]?.[pick], m.key)}
          </Table.Summary.Cell>
        </Fragment>
      ))}
      {ratios.map((c, i) => (
        <Table.Summary.Cell key={c.key} index={ratioStart + i} align="right">
          {pick === "total" ? fmtNum(data.intensity?.[c.key], c.digits) : ""}
        </Table.Summary.Cell>
      ))}
    </Table.Summary.Row>
  );

  return (
    <div className="card sf-table-card">
      <Table<DailyRow>
        rowKey="date" size="small" bordered columns={columns} dataSource={data.rows}
        pagination={false} scroll={{ x: "max-content" }}
        rowClassName={(r) => (isToday(r, data.metrics) ? "sf-row-today" : "")}
        summary={() => (!data.rows.length ? null : (
          <>
            {summaryRow("Tổng", "total")}
            {summaryRow("TB/ngày đủ số", "avg_per_day")}
          </>
        ))}
      />
    </div>
  );
}
