/* Biểu tượng thiết bị theo `kind`, bám màn SCADA RELCO: khung thép xám, bộ phận chuyển động XANH LÁ khi
   chạy / xám thép khi dừng (class `pl-part*` — màu + chuyển động ở plant-devices.css, theo class
   run/stop/empty của nhóm cha). Vẽ trong khung cục bộ (0,0)–(w,h). Máy cán ở plant-icons-crushers.tsx;
   bể khuấy · bơm · mô-tơ ở plant-icons-machines.tsx; zone · counter là ô số (PlantNode). */

import type { ReactElement } from "react";

import type { PlantNodeKind } from "../../../../../lib/smart-factory-client";
import { Crusher } from "./plant-icons-crushers";
import { Motor, Pump, Tank } from "./plant-icons-machines";
import { Fins, type IconProps, RoundMotor, Spin, downDir, range } from "./plant-icon-parts";

/** Nghiêng dưới mức này (độ) coi là băng nằm ngang → mô-tơ lớn liền đầu băng, 2 chân đỡ. */
const FLAT_DEG = 5;
/** Góc nghiêng các vệt xoắn của vít tải. */
const SCREW_SKEW_DEG = -35;

/** Máy khuấy (MLM, TKMM) như RELCO: hộp mô-tơ vuông (vòng bu-lông, chân khoét ∩) + gối đỡ teal ngồi trên
 *  mép máng · trục ngang · chân vịt 4 cánh LỚN quay (cánh đi sau hộp mô-tơ). Bán kính cánh lấy tối đa phần
 *  khung còn lại bên trái hộp. */
function Mixer({ w, h }: IconProps) {
  const s = Math.min(w, h);
  const bw = s * 0.4, bh = s * 0.38, hy = h * 0.5, rimY = hy + s * 0.1;
  const bx = w - bw, by = rimY - bh;
  const r = Math.max(8, Math.min((w - bw) / 1.5, hy, h - hy));
  const hx = bx - r * 0.5;
  const arch = bw * 0.2, side = bw / 2 - arch;
  const ringR = bw * 0.27, rcx = bx + bw / 2, rcy = by + bh * 0.42;
  return (
    <>
      <Spin cx={hx} cy={hy} r={r}>
        {[30, 120, 210, 300].map((a) => {
          const t = (a * Math.PI) / 180;
          return <line key={a} x1={0} y1={0} x2={r * Math.cos(t)} y2={r * Math.sin(t)} className="pl-part-line"
            strokeWidth={Math.max(3, s * 0.045)} strokeLinecap="round" />;
        })}
      </Spin>
      <line x1={hx} y1={hy} x2={bx + 2} y2={hy} className="pl-shaft" strokeWidth={4} />
      <path d={`M${hx - s * 0.06} ${hy + 2} h${s * 0.12} l${s * 0.05} ${rimY - hy - 2} h${-s * 0.22} Z`}
        className="pl-teal" />
      <circle cx={hx} cy={hy} r={s * 0.065} className="pl-part-r" />
      <path d={`M${bx} ${by} h${bw} v${bh} h${-side} a${arch} ${arch} 0 0 0 ${-2 * arch} 0 h${-side} Z`}
        className="pl-part" />
      <circle cx={rcx} cy={rcy} r={ringR} className="pl-ring" />
      {range(8).map((i) => {
        const a = (i * Math.PI) / 4;
        return <circle key={i} cx={rcx + ringR * Math.cos(a)} cy={rcy + ringR * Math.sin(a)} r={1.7}
          className="pl-bolt" />;
      })}
    </>
  );
}

/** Băng tải (BTTL, BTCS, BTCLM, TL): w = chiều dài, h = bề dày. Khung thép + con lăn · dải băng xanh có
 *  gân chạy · puly đuôi · chân đỡ thẳng đứng. Băng nghiêng: puly đầu nhỏ + mô-tơ tròn trên giá đỡ phía
 *  trên đầu băng (như RELCO); băng nằm ngang: mô-tơ lớn liền đầu băng. */
function Conveyor({ w, h, angle }: IconProps) {
  const r = h / 2, belt = h * 0.3;
  const n = Math.max(2, Math.round((w - 2 * r) / 34));
  const [dx, dy] = downDir(angle);
  const flat = Math.abs(angle) < FLAT_DEG;
  const legs = flat ? [0.12, 0.78] : [0.62];
  const legLen = flat ? h * 1.1 : Math.min(70, w * 0.24);
  // Giá mô-tơ: lùi về sau đầu băng một chút rồi dựng thẳng lên (hướng "lên" của thế giới).
  const bx = w - r * 2.6, by = r, mx = bx - dx * h * 2, my = by - dy * h * 2;
  return (
    <>
      {legs.map((f) => (
        <line key={f} x1={w * f} y1={h * 0.7} x2={w * f + dx * legLen} y2={h * 0.7 + dy * legLen}
          className="pl-leg" strokeWidth={3.5} />
      ))}
      {!flat && <line x1={bx} y1={by} x2={mx} y2={my} className="pl-leg" strokeWidth={4} />}
      <rect x={r * 0.5} y={h * 0.3} width={w - r} height={h * 0.45} rx={2} className="pl-frame" />
      {range(n + 1).map((i) => (
        <circle key={i} cx={r + ((w - 2 * r) * i) / n} cy={h * 0.64} r={h * 0.12} className="pl-roller" />
      ))}
      <line x1={r} y1={belt} x2={w - r} y2={belt} className="pl-part-line" strokeWidth={h * 0.3}
        strokeLinecap="round" />
      <line x1={r} y1={belt} x2={w - r} y2={belt} className="pl-flow pl-cleat" strokeWidth={h * 0.3} />
      <RoundMotor cx={r} cy={r} r={r * 0.95} />
      <RoundMotor cx={w - r} cy={r} r={flat ? h * 0.72 : r * 0.8} />
      {!flat && <RoundMotor cx={mx} cy={my} r={h * 0.7} />}
    </>
  );
}

/** Vít tải (VT, VTN) như RELCO: máng thép có SỌC CHÉO xanh tươi khi chạy (trượt dọc ống) / xám khi dừng ·
 *  đầu trên: hộp số thép + mô-tơ trụ có gân + nắp teal. */
function Screw({ w, h }: IconProps) {
  const hl = h * 2.4, end = w - hl;
  const t = Math.tan((SCREW_SKEW_DEG * Math.PI) / 180);
  return (
    <>
      <rect x={0} y={h * 0.12} width={end + 2} height={h * 0.76} rx={h * 0.3} className="pl-steel" />
      <line x1={h * 0.3} y1={h / 2} x2={end - h * 0.1} y2={h / 2} className="pl-rail" strokeWidth={h * 0.12} />
      <g transform={`translate(${(-h / 2) * t} 0) skewX(${SCREW_SKEW_DEG})`}>
        <line x1={h * 0.45} y1={h / 2} x2={end - h * 0.45} y2={h / 2} className="pl-flow pl-part-line"
          strokeWidth={h * 0.6} />
      </g>
      <rect x={end} y={-h * 0.12} width={hl * 0.34} height={h * 1.24} rx={3} className="pl-steel" />
      <rect x={end + hl * 0.34} y={h * 0.06} width={hl * 0.5} height={h * 0.88} rx={h * 0.2} className="pl-part" />
      <Fins x={end + hl * 0.34} y={h * 0.06} w={hl * 0.5} h={h * 0.88} n={3} vertical />
      <rect x={w - hl * 0.16} y={h * 0.16} width={hl * 0.16} height={h * 0.68} rx={2} className="pl-teal" />
    </>
  );
}

/** Quạt (QC, QN, QHL, QK): vỏ tròn thép trên đế · 4 cánh cong quay. */
function Fan({ w, h }: IconProps) {
  const cx = w / 2, r = Math.min(w, h) * 0.42, cy = r + 2;
  const blade = `M0 0 C${r * 0.1} ${-r * 0.45} ${r * 0.5} ${-r * 0.72} ${r * 0.72} ${-r * 0.42}`
    + ` C${r * 0.55} ${-r * 0.2} ${r * 0.28} ${-r * 0.06} 0 0 Z`;
  return (
    <>
      <path d={`M${cx - r * 0.5} ${cy + r * 0.7} L${cx + r * 0.5} ${cy + r * 0.7} L${cx + r * 0.72} ${h}`
        + ` L${cx - r * 0.72} ${h} Z`} className="pl-steel" />
      <circle cx={cx} cy={cy} r={r} className="pl-steel" strokeWidth={2.5} />
      <circle cx={cx} cy={cy} r={r * 0.84} className="pl-well" />
      <Spin cx={cx} cy={cy} r={r * 0.8}>
        {[0, 90, 180, 270].map((a) => <path key={a} d={blade} className="pl-part" transform={`rotate(${a})`} />)}
        <circle r={r * 0.15} className="pl-hub" />
      </Spin>
    </>
  );
}

const ICONS: Partial<Record<PlantNodeKind, (p: IconProps) => ReactElement>> = {
  mixer: Mixer, conveyor: Conveyor, screw: Screw, crusher: Crusher,
  tank: Tank, pump: Pump, fan: Fan, motor: Motor,
};

/** Kind lạ (bố cục mới hơn web) → vẽ như mô-tơ thay vì bỏ trống. */
export function DeviceIcon({ kind, ...p }: IconProps & { kind: PlantNodeKind }) {
  const Icon = ICONS[kind] ?? Motor;
  return <Icon {...p} />;
}
