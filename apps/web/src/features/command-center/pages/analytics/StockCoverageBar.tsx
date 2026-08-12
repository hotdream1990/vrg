/* Dải ĐỘ PHỦ của ảnh chụp tồn kho: người xem phải biết tổng đang gồm bao nhiêu đơn vị và đơn vị nào
   chưa có số — nếu không sẽ tưởng con số tổng là đầy đủ. Ngày lấy số của từng dòng đã có sẵn trong
   bảng nên không điểm mặt riêng đơn vị "số cũ".

   Đơn vị khai "không phát sinh tồn kho để khai" KHÔNG hiện ra (đã nộp, chẳng có gì để nhắc) → phải
   TRỪ khỏi mẫu số, nếu không "45/57 có số" + "9 chưa có số" hụt mất mấy đơn vị, đọc như đếm sai. */

import { CheckCircleOutlined, WarningOutlined } from "@ant-design/icons";
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
  const { units_counted: counted, missing } = coverage;
  const expected = coverage.units_expected - (coverage.no_stock ?? []).length;
  const full = counted >= expected;

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
      {!!missing.length && item("var(--danger)", <WarningOutlined />,
        `${missing.length} đơn vị chưa có số`,
        missing.map((m) => m.company + (m.has_factory ? "" : " (không có nhà máy)")).join("\n"))}
    </div>
  );
}
