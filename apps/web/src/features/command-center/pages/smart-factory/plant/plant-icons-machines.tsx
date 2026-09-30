/* Biểu tượng máy lớn, bám màn RELCO: bể khuấy thép · bơm · mô-tơ (máy cán ở plant-icons-crushers.tsx).
   Màu theo class (plant-devices.css); khung cục bộ (0,0)–(w,h). */

import { Fins, type IconProps, Spin, range } from "./plant-icon-parts";

/** Bể khuấy (QM): bể thép dài (thành đứng, đáy vát vào giữa có ống xả, trụ đỡ xuống đất) · thanh khuấy
 *  NGANG kiểu lược dọc mép trên (răng dọc cách đều, vệt chạy khi quay) · mô-tơ trụ + hộp số giữa mép. */
export function Tank({ w, h }: IconProps) {
  const rim = h * 0.4, wall = h * 0.78, bot = h * 0.9;
  const barY = rim + h * 0.075, bar = h * 0.085, tooth = h * 0.2;
  const blk = h * 0.15, mw = Math.min(h * 0.24, w * 0.1);
  const posts = range(6).map((i) => w * (0.03 + (0.94 * i) / 5));
  const teeth = Math.max(4, Math.round(w / 22));
  return (
    <>
      {posts.map((x) => <line key={x} x1={x} y1={rim} x2={x} y2={h} className="pl-leg" strokeWidth={3} />)}
      <rect x={w * 0.44} y={bot - 1} width={w * 0.12} height={h * 0.08} className="pl-steel" />
      <path d={`M0 ${rim} L${w} ${rim} L${w * 0.975} ${wall} L${w * 0.62} ${bot} L${w * 0.38} ${bot}`
        + ` L${w * 0.025} ${wall} Z`} className="pl-tank" />
      {posts.slice(1, -1).map((x) => (
        <line key={x} x1={x} y1={rim + 3} x2={x} y2={wall} className="pl-basin-rib" />
      ))}
      <line x1={w * 0.025} y1={wall} x2={w * 0.975} y2={wall} className="pl-basin-rib" />
      <rect x={-3} y={rim - 3} width={w + 6} height={6} rx={2} className="pl-steel" />
      {range(teeth - 1).map((i) => {
        const x = (w * (i + 1)) / teeth;
        return <rect key={i} x={x - 1.6} y={barY - tooth / 2} width={3.2} height={tooth} rx={1} className="pl-part" />;
      })}
      <rect x={w * 0.02} y={barY - bar / 2} width={w * 0.96} height={bar} rx={bar / 2} className="pl-part" />
      <line x1={w * 0.04} y1={barY} x2={w * 0.96} y2={barY} className="pl-flow pl-part-dark" strokeWidth={bar * 0.35} />
      <rect x={w / 2 - blk / 2} y={barY - blk / 2} width={blk} height={blk} rx={2} className="pl-part" />
      <rect x={w / 2 - mw / 2} y={h * 0.04} width={mw} height={barY - blk / 2 - h * 0.04} rx={3} className="pl-part" />
      <Fins x={w / 2 - mw / 2} y={h * 0.04} w={mw} h={barY - blk / 2 - h * 0.04} n={3} />
      <rect x={w / 2 - mw * 0.35} y={0} width={mw * 0.7} height={h * 0.05} rx={1.5} className="pl-part" />
    </>
  );
}

/** Bơm (BC): buồng xoắn teal trên cột, cánh bơm quay · ống xả · mô-tơ dưới chân · đế. */
export function Pump({ w, h }: IconProps) {
  const cx = w / 2, vr = Math.min(w * 0.36, h * 0.2), vy = vr + 2;
  return (
    <>
      <rect x={w * 0.06} y={h * 0.92} width={w * 0.88} height={h * 0.08} rx={2} className="pl-foot" />
      <rect x={cx - w * 0.3} y={h * 0.58} width={w * 0.6} height={h * 0.33} rx={5} className="pl-part" />
      <Fins x={cx - w * 0.3} y={h * 0.58} w={w * 0.6} h={h * 0.33} n={3} />
      <rect x={cx - w * 0.1} y={vy} width={w * 0.2} height={h * 0.58 - vy} className="pl-teal" />
      <rect x={cx} y={vy - vr * 0.95} width={w * 0.5} height={vr * 0.45} className="pl-steel" />
      <circle cx={cx} cy={vy} r={vr} className="pl-teal" />
      <Spin cx={cx} cy={vy} r={vr * 0.62}>
        <circle r={vr * 0.6} className="pl-roll-face" />
        {range(3).map((i) => (
          <line key={i} x1={0} y1={0} x2={vr * 0.5 * Math.cos((i * 2 * Math.PI) / 3)}
            y2={vr * 0.5 * Math.sin((i * 2 * Math.PI) / 3)} className="pl-roll-spoke" />
        ))}
        <circle r={vr * 0.18} className="pl-hub" />
      </Spin>
    </>
  );
}

/** Mô-tơ (SR, XDT, kind lạ): thân trụ nằm có gân · nắp quạt · hộp đấu dây · trục ra · chân trên đế. */
export function Motor({ w, h }: IconProps) {
  const bx = w * 0.16, by = h * 0.3, bw = w * 0.56, bh = h * 0.44;
  return (
    <>
      <rect x={w * 0.04} y={h * 0.82} width={w * 0.92} height={h * 0.07} rx={2} className="pl-foot" />
      <path d={`M${bx + bw * 0.1} ${by + bh} L${bx + bw * 0.9} ${by + bh} L${bx + bw} ${h * 0.82}`
        + ` L${bx} ${h * 0.82} Z`} className="pl-steel" />
      <rect x={w * 0.72} y={h * 0.49} width={w * 0.2} height={h * 0.06} className="pl-steel" />
      <rect x={w * 0.06} y={by + bh * 0.08} width={w * 0.12} height={bh * 0.84} rx={4} className="pl-part" />
      <rect x={bx} y={by} width={bw} height={bh} rx={h * 0.07} className="pl-part" />
      <Fins x={bx} y={by} w={bw} h={bh} n={5} />
      <rect x={bx + bw} y={by + bh * 0.14} width={w * 0.07} height={bh * 0.72} rx={3} className="pl-part" />
      <rect x={bx + bw * 0.34} y={by - h * 0.09} width={bw * 0.3} height={h * 0.09} rx={2} className="pl-part" />
    </>
  );
}
