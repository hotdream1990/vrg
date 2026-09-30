/* Một thiết bị trên sơ đồ, vẽ 2 lớp để ô số không bị hình thiết bị khác đè:
   - PlantNodeShape: biểu tượng (xoay theo `angle`; class run/stop/unknown + empty quyết định màu và chuyển
     động) — hoặc ô số lớn với zone (nhiệt độ buồng sấy) / counter (số bành).
   - PlantNodeInfo: nhãn mã · đèn "R" chạy/dừng · ô số trắng Hz/A; nhiệt độ. Bố cục v2 khai `info_xy` /
     `temps_xy` → đặt ĐÚNG toạ độ đó (nhãn canh trái như RELCO); không khai → tự đặt ở cạnh `label_pos`,
     nhiệt độ ở cạnh đối diện. */

import type { PlantNode, PlantValues } from "../../../../../lib/smart-factory-client";
import { fmtNum } from "../smart-factory-format";
import {
  HOT_TEMP_C, VALUE_DIGITS, blockAt, hasNoData, opposite, outerBox, runState, valueOf,
} from "./plant-format";
import { DeviceIcon } from "./plant-icons";

// Kích thước theo đơn vị của khung khu (≈ px màn SCADA 1:1) — hơi lớn hơn màn RELCO (ô 48×15) vì web
// thường thu nhỏ khung cho vừa card. Khối nhãn: rộng BLOCK_W, cao LABEL_H + số dòng × ROW.
const BOX_W = 58;
const BOX_H = 18;
const ROW = 21;
const UNIT_W = 22;
const LAMP_W = 15;
const LAMP_R = 6.5;
const LABEL_H = 17;
const BLOCK_W = LAMP_W + BOX_W + 3 + UNIT_W;
const TEMP_W = BOX_W + 3 + UNIT_W;
const TEMP_GAP = 6;
const TILE_FONT_MAX = 32;

/** Băng tải · vít tải có thêm đèn "!" ở dòng thứ hai (A) như RELCO: xanh khi chạy, đỏ khi dừng. */
const FAULT_LAMP_KINDS = new Set<PlantNode["kind"]>(["conveyor", "screw"]);

/** Đèn tròn có chữ ("R" chạy/dừng · "!" dừng = đỏ) tại tâm (x, y) của khối nhãn. */
function Lamp({ y, state, text, fault }: { y: number; state: string; text: string; fault?: boolean }) {
  return (
    <g transform={`translate(${LAMP_R} ${y})`} className={`pl-lamp ${state}${fault ? " fault" : ""}`}>
      <circle r={LAMP_R} />
      <text y={3.2} textAnchor="middle">{text}</text>
    </g>
  );
}

/** Thiết bị vẽ thành ô số lớn (nhãn nằm trong ô) thay vì biểu tượng + ô số rời. */
export const isTile = (n: PlantNode) => n.kind === "zone" || n.kind === "counter";

type NodeProps = { node: PlantNode; values: PlantValues };

type BoxProps = { x: number; y: number; value: number | null; unit: string; hot?: boolean };

/** Ô số trắng viền kiểu RELCO: số căn giữa ô, đơn vị ngoài ô. */
function ValueBox({ x, y, value, unit, hot }: BoxProps) {
  const cls = `pl-box${hot ? " hot" : ""}${value == null ? " empty" : ""}`;
  return (
    <g transform={`translate(${x} ${y})`} className={cls}>
      <rect width={BOX_W} height={BOX_H} rx={3} />
      <text x={BOX_W / 2} y={BOX_H - 4.5} textAnchor="middle" className="pl-num">{fmtNum(value, VALUE_DIGITS)}</text>
      <text x={BOX_W + 3} y={BOX_H - 4.5} className="pl-unit">{unit}</text>
    </g>
  );
}

/** zone: nhiệt độ buồng sấy · counter: số bành (số nguyên). */
function ValueTile({ node, values }: NodeProps) {
  const zone = node.kind === "zone";
  const m = node.metrics?.[0];
  const tag = zone ? (node.temps?.[0]?.tag ?? m?.tag) : m?.tag;
  const unit = zone ? "°C" : (m?.unit ?? "");
  const v = valueOf(values, tag);
  const fs = Math.max(14, Math.min((node.h - 20) * 0.5, node.w / 6, TILE_FONT_MAX));
  return (
    <g transform={`translate(${node.x} ${node.y})`} className={`pl-tile ${node.kind}${v == null ? " empty" : ""}`}>
      <rect width={node.w} height={node.h} rx={8} />
      <text x={8} y={15} className="pl-tile-label">{node.label}</text>
      <text x={node.w / 2} y={20 + (node.h - 20) / 2 + fs * 0.35} textAnchor="middle" fontSize={fs}
        className="pl-tile-num">
        {fmtNum(v, zone ? VALUE_DIGITS : 0)}
        {v != null && <tspan dx={4} fontSize={fs * 0.45} className="pl-unit">{unit}</tspan>}
      </text>
    </g>
  );
}

export function PlantNodeShape({ node, values }: NodeProps) {
  if (isTile(node)) return <ValueTile node={node} values={values} />;
  const { x, y, w, h } = node;
  const a = node.angle ?? 0;
  const cls = `pl-dev ${runState(node, values)}${hasNoData(node, values) ? " empty" : ""}`;
  return (
    <g className={cls} transform={`translate(${x} ${y})${a ? ` rotate(${a} ${w / 2} ${h / 2})` : ""}`}>
      <DeviceIcon kind={node.kind} w={w} h={h} angle={a} variant={node.variant} />
    </g>
  );
}

export function PlantNodeInfo({ node, values }: NodeProps) {
  if (isTile(node)) return null;
  const side = node.label_pos ?? "top";
  const box = outerBox(node);
  const metrics = node.metrics ?? [];
  const temps = node.temps ?? [];
  const [bx, by] = node.info_xy ?? blockAt(box, side, BLOCK_W, LABEL_H + metrics.length * ROW);
  // 4 ô nhiệt độ (ổ trục trên/dưới × trái/phải) xếp 2×2 như RELCO — xếp dọc thì dài gấp đôi, tràn đáy khung.
  const cols = node.temps_cols ?? (temps.length >= 4 ? 2 : 1);
  const rows = Math.ceil(temps.length / cols);
  const [tx, ty] = node.temps_xy
    ?? blockAt(box, opposite(side), cols * TEMP_W + (cols - 1) * TEMP_GAP, rows * ROW - (ROW - BOX_H));
  const lampY = metrics.length ? LABEL_H + BOX_H / 2 : LABEL_H / 2;
  const state = runState(node, values);
  return (
    <>
      <g transform={`translate(${bx} ${by})`}>
        {node.info_xy
          ? <text x={LAMP_W} y={14} className="pl-label">{node.label}</text>
          : <text x={LAMP_W + BOX_W / 2} y={14} textAnchor="middle" className="pl-label">{node.label}</text>}
        {node.status_tag && <Lamp y={lampY} state={state} text="R" />}
        {node.status_tag && metrics.length > 1 && FAULT_LAMP_KINDS.has(node.kind) && (
          <Lamp y={LABEL_H + ROW + BOX_H / 2} state={state} text="!" fault />
        )}
        {metrics.map((m, i) => (
          <ValueBox key={m.tag} x={LAMP_W} y={LABEL_H + i * ROW} value={valueOf(values, m.tag)} unit={m.unit} />
        ))}
      </g>
      {temps.length > 0 && (
        <g transform={`translate(${tx} ${ty})`}>
          {temps.map((t, i) => {
            const v = valueOf(values, t.tag);
            return <ValueBox key={t.tag} x={(i % cols) * (TEMP_W + TEMP_GAP)} y={Math.floor(i / cols) * ROW}
              value={v} unit="°C" hot={v != null && v >= HOT_TEMP_C} />;
          })}
        </g>
      )}
    </>
  );
}
