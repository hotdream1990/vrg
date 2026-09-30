/* Khung SVG của một khu: viewBox = width × height của khu, co VỪA bề ngang card (giữ tỉ lệ); chỉ màn
   ≤ 768px mới giữ bề rộng tối thiểu (`--pl-min-w`, chữ còn đọc được) và cuộn NGANG bên trong khung.
   Thứ tự vẽ: trang trí → đường nối → thiết bị → nhãn/ô số (ô số luôn nằm trên mọi hình) → bảng tiêu thụ
   trong ngày (khu khai `usage_box`, cần `usage` = nhà máy + các chỉ số nhà máy có).
   Chưa có số của khu (lần đầu / vừa đổi khu) → Spin; mất kết nối / số cũ (`dim`) → cả sơ đồ xám. */

import { Spin, Tooltip } from "antd";
import { type CSSProperties, useMemo } from "react";

import type { MetricKey, PlantArea, PlantNode, PlantValues } from "../../../../../lib/smart-factory-client";
import { center } from "./plant-format";
import { PlantDecorShape } from "./PlantDecor";
import { PlantNodeInfo, PlantNodeShape, isTile } from "./PlantNode";
import PlantNodeTip from "./PlantNodeTip";
import PlantUsageBox from "./PlantUsageBox";
import { PlantDefs } from "./plant-defs";
import "./plant-devices.css";

const NO_VALUES: PlantValues = {};
/** Màn ≤ 768px: không thu khung nhỏ hơn tỉ lệ này — card hẹp hơn thì cuộn ngang trong khung. */
const MIN_SCALE = 0.65;
const TIP_DELAY_S = 0.15;

type Props = {
  area: PlantArea; values: PlantValues | null; failed: boolean; dim: boolean;
  usage: { factoryId: number; metrics: MetricKey[] } | null;
};

/** Rê chuột lên hình hoặc ô số của thiết bị → bảng tag · giá trị · giờ đọc. */
function WithTip({ node, values, children }: { node: PlantNode; values: PlantValues; children: JSX.Element }) {
  return (
    <Tooltip title={<PlantNodeTip node={node} values={values} />} mouseEnterDelay={TIP_DELAY_S}>
      <g className="pl-node">{children}</g>
    </Tooltip>
  );
}

export default function PlantAreaDiagram({ area, values, failed, dim, usage }: Props) {
  const vals = values ?? NO_VALUES;
  const byId = useMemo(() => new Map(area.nodes.map((n) => [n.id, n])), [area]);
  const size = {
    aspectRatio: `${area.width} / ${area.height}`,
    "--pl-min-w": `${Math.round(area.width * MIN_SCALE)}px`,
  } as CSSProperties;

  return (
    <Spin spinning={values == null && !failed}>
      <div className={`pl-scroll${dim ? " pl-dim" : ""}`}>
        <svg className="pl-svg" viewBox={`0 0 ${area.width} ${area.height}`} role="img" aria-label={area.label}
          style={size}>
          <PlantDefs />
          {(area.decor ?? []).map((d, i) => <PlantDecorShape key={`d${i}`} d={d} />)}
          {(area.links ?? []).map(([a, b]) => {
            const na = byId.get(a);
            const nb = byId.get(b);
            if (!na || !nb) return null;
            const [x1, y1] = center(na);
            const [x2, y2] = center(nb);
            return <line key={`${a}-${b}`} x1={x1} y1={y1} x2={x2} y2={y2} className="pl-link" />;
          })}
          {area.nodes.map((n) => (
            <WithTip key={`s-${n.id}`} node={n} values={vals}><PlantNodeShape node={n} values={vals} /></WithTip>
          ))}
          {area.nodes.filter((n) => !isTile(n)).map((n) => (
            <WithTip key={`i-${n.id}`} node={n} values={vals}><PlantNodeInfo node={n} values={vals} /></WithTip>
          ))}
          {area.usage_box && usage && usage.metrics.length > 0 && (
            <PlantUsageBox box={area.usage_box} factoryId={usage.factoryId} metrics={usage.metrics} />
          )}
        </svg>
      </div>
    </Spin>
  );
}
