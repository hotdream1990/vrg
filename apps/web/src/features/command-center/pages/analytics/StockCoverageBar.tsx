/* Dải ĐỘ PHỦ của ảnh chụp tồn kho: người xem phải biết tổng đang gồm bao nhiêu đơn vị, đơn vị nào
   đang lấy số cũ, đơn vị nào chưa có số — nếu không sẽ tưởng con số tổng là đầy đủ. */

import {
  CheckCircleOutlined, ClockCircleOutlined, MinusCircleOutlined, WarningOutlined,
} from "@ant-design/icons";
import { Tooltip } from "antd";

import { dmy } from "../../../../lib/date";
import type { StockCoverage } from "../../../../lib/unit-analytics-client";

type Props = { asOf: string; maxAgeDays: number; coverage: StockCoverage };

const item = (color: string, icon: React.ReactNode, text: string, tip?: string) => (
  <Tooltip title={tip} key={text}>
    <span style={{ color, display: "inline-flex", alignItems: "center", gap: 6,
                   cursor: tip ? "help" : "default" }}>
      {icon}{text}
    </span>
  </Tooltip>
);

export default function StockCoverageBar({ asOf, maxAgeDays, coverage }: Props) {
  const { units_expected: expected, units_counted: counted, stale, missing } = coverage;
  const empty = coverage.no_stock ?? [];
  const full = counted >= expected && !stale.length;

  return (
    <div className="card" style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap",
                                   fontSize: 13, marginBottom: 12 }}>
      <span>
        Ảnh chụp tại ngày chốt <b>{dmy(asOf)}</b>
        <span style={{ color: "var(--muted)" }}>
          {maxAgeDays > 0 ? ` · lấy số cũ tối đa ${maxAgeDays} ngày` : " · chỉ lấy số nhập đúng ngày"}
        </span>
      </span>
      {item(full ? "var(--accent)" : "inherit", <CheckCircleOutlined />,
            `${counted}/${expected} đơn vị có số`)}
      {!!stale.length && item("var(--warn)", <ClockCircleOutlined />,
        `${stale.length} đơn vị số cũ`,
        stale.map((s) => `${s.company}: ${dmy(s.as_of)} (cũ ${s.age_days} ngày)`).join("\n"))}
      {!!empty.length && item("var(--muted)", <MinusCircleOutlined />,
        `${empty.length} đơn vị khai không phát sinh`,
        empty.map((e) => `${e.company}: ${dmy(e.as_of)}`).join("\n"))}
      {!!missing.length && item("var(--danger)", <WarningOutlined />,
        `${missing.length} đơn vị chưa có số`,
        missing.map((m) => m.company + (m.has_factory ? "" : " (không có nhà máy)")).join("\n"))}
    </div>
  );
}
