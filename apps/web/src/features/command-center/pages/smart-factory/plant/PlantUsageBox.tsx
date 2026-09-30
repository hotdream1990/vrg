/* Bảng "THỐNG KÊ TIÊU THỤ TRONG NGÀY" vẽ NGAY TRONG khung sơ đồ tại `usage_box` của khu (như góc phải trên
   màn RELCO): nền trắng viền đậm · tiêu đề in hoa căn giữa · cột Điện · Nước · Bành mủ · dòng Hôm qua / Hôm
   nay · số xanh đậm (điện/nước 1 số lẻ, bành số nguyên). Số lấy từ usePlantDailyUsage (chung với ô trên
   trang). `memo`: khung sơ đồ vẽ lại mỗi nhịp 5 s — bảng này chỉ đổi theo nhịp 60 s của chính nó. */

import { memo } from "react";

import type { MetricKey, PlantArea } from "../../../../../lib/smart-factory-client";
import { fmtNum } from "../smart-factory-format";
import { usePlantDailyUsage } from "./use-plant-daily-usage";

const HEAD: Record<MetricKey, string> = { energy: "Điện (kWh)", water: "Nước (m³)", bales: "Bành mủ" };
const DIGITS: Record<MetricKey, number> = { energy: 1, water: 1, bales: 0 };
/** Cột nhãn dòng (Hôm qua / Hôm nay) chiếm phần này bề ngang bảng; các cột số chia đều phần còn lại. */
const LABEL_COL = 0.2;
const PAD_X = 0.03;
/** Cỡ chữ theo chiều cao bảng (RELCO ≈ 130 đơn vị cao) — chặn trên/dưới cho bảng khai quá to/nhỏ. */
const FONT_RATIO = 0.11;
const FONT_MIN = 11;
const FONT_MAX = 18;

type Props = { box: NonNullable<PlantArea["usage_box"]>; factoryId: number; metrics: MetricKey[] };

function PlantUsageBox({ box, factoryId, metrics }: Props) {
  const { cols, rows, failed } = usePlantDailyUsage(factoryId, metrics);
  const { x, y, w, h } = box;
  const fs = Math.max(FONT_MIN, Math.min(h * FONT_RATIO, FONT_MAX));
  const colW = (w * (1 - LABEL_COL - PAD_X)) / Math.max(cols.length, 1);
  const colX = (i: number) => w * LABEL_COL + colW * (i + 0.5);
  // 4 hàng chữ: tiêu đề · đầu cột · Hôm qua · Hôm nay (đường chân chữ).
  const lineY = [0.22, 0.46, 0.7, 0.9].map((f) => h * f);
  return (
    <g transform={`translate(${x} ${y})`} className={`pl-usagebox${failed ? " stale" : ""}`}>
      <rect width={w} height={h} className="pl-usagebox-frame" />
      <text x={w / 2} y={lineY[0]} textAnchor="middle" fontSize={fs} className="pl-usagebox-title">
        THỐNG KÊ TIÊU THỤ TRONG NGÀY
      </text>
      {cols.map((k, i) => (
        <text key={k} x={colX(i)} y={lineY[1]} textAnchor="middle" fontSize={fs * 0.92} className="pl-usagebox-head">
          {HEAD[k]}
        </text>
      ))}
      {rows.map(({ label, row }, r) => (
        <g key={label}>
          <text x={w * PAD_X} y={lineY[2 + r]} fontSize={fs * 0.92} className="pl-usagebox-head">{label}</text>
          {cols.map((k, i) => (
            <text key={k} x={colX(i)} y={lineY[2 + r]} textAnchor="middle" fontSize={fs * 1.08}
              className="pl-usagebox-num">
              {fmtNum(row?.[k]?.used, DIGITS[k])}
            </text>
          ))}
        </g>
      ))}
    </g>
  );
}

export default memo(PlantUsageBox);
