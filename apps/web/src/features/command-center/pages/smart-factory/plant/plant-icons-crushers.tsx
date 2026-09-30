/* Máy cán/băm (kind `crusher`), bám màn RELCO. `variant` chọn dáng: "mill" = tháp cán cao (CM) · "creper" =
   máy 2 trục nhìn nghiêng (CCS, C3T). Không khai → theo tỉ lệ khung (cao hơn rộng quá TALL_RATIO = tháp cán,
   còn lại máy cán 2 trục nhìn thẳng). Màu theo class (plant-devices.css); khung cục bộ (0,0)–(w,h). */

import { Fins, type IconProps, Roll, RoundMotor, Spin } from "./plant-icon-parts";

const TALL_RATIO = 1.2;

/** Tháp cán (CM): phễu trụ teal hơi loe · thân teal (phần dưới rộng sang trái) có đĩa rô-to lớn — 2 cánh
 *  cong xanh quay khi chạy · máng xả bên phải · giá thép 4 chân cao xuống đất, 2 tầng giằng. */
function Mill({ w, h }: IconProps) {
  const R = Math.min(w * 0.31, h * 0.11), cx = w * 0.56, cy = h * 0.4, r = R * 0.9;
  // Cánh xoáy hình dấu phẩy (2 cánh đối xứng thành chữ S như rô-to RELCO).
  const blade = `M0 0 C${r * 0.15} ${-r * 0.95} ${r * 1.05} ${-r * 0.75} ${r * 0.95} ${r * 0.1}`
    + ` C${r * 0.7} ${-r * 0.3} ${r * 0.3} ${-r * 0.2} 0 0 Z`;
  const standY = h * 0.6, legW = w * 0.07;
  return (
    <>
      {[0.3, 0.74].map((f) => (
        <rect key={f} x={w * f} y={standY} width={legW * 0.7} height={h - standY - 2} className="pl-steel" />
      ))}
      {[0.76, 0.9].map((f) => (
        <rect key={f} x={w * 0.14} y={h * f} width={w * 0.83} height={h * 0.018} className="pl-steel" />
      ))}
      {[0.12, 0.9].map((f) => (
        <g key={f}>
          <rect x={w * f} y={standY} width={legW} height={h - standY} className="pl-steel" />
          <rect x={w * f - 2} y={h - 3} width={legW + 4} height={3} className="pl-foot" />
        </g>
      ))}
      <rect x={w * 0.08} y={standY - 1} width={w * 0.9} height={h * 0.025} className="pl-steel" />
      <path d={`M${w * 0.93} ${h * 0.52} L${w * 1.12} ${h * 0.6} L${w * 1.12} ${h * 0.625} L${w * 0.93} ${h * 0.56} Z`}
        className="pl-steel" />
      <path d={`M${w * 0.17} 0 L${w * 0.95} 0 L${w * 0.91} ${h * 0.31} L${w * 0.21} ${h * 0.31} Z`}
        className="pl-teal-h" />
      <rect x={w * 0.14} y={0} width={w * 0.84} height={h * 0.025} rx={1.5} className="pl-teal" />
      <rect x={w * 0.21} y={h * 0.3} width={w * 0.7} height={h * 0.16} className="pl-teal" />
      <rect x={0} y={h * 0.44} width={w * 0.93} height={h * 0.16} className="pl-teal" />
      <line x1={w * 0.21} y1={h * 0.305} x2={w * 0.91} y2={h * 0.305} className="pl-seam" />
      <circle cx={cx} cy={cy} r={R} className="pl-window" strokeWidth={2} />
      <Spin cx={cx} cy={cy} r={r}>
        {[0, 180].map((a) => <path key={a} d={blade} className="pl-part" transform={`rotate(${a})`} />)}
        <circle r={R * 0.24} className="pl-hub" />
      </Spin>
    </>
  );
}

/** Máy 2 trục nhìn nghiêng (CCS, C3T): phễu thép · thân teal bo tròn · 2 trục cán lớn (vành thép + vòng teal +
 *  mặt quay, tâm xanh khi chạy) · mô-tơ tròn trên tay đỡ góc phải · 2 chân teal · dầm thép + 4 chân tăng. */
function Creper({ w, h }: IconProps) {
  const r = Math.min(w * 0.19, h * 0.2), ry = h * 0.43;
  const legs = [[0.03, 0.3, 0.1, 0.25], [0.7, 0.97, 0.75, 0.9]];
  return (
    <>
      {[0.1, 0.27, 0.72, 0.89].map((f) => (
        <g key={f}>
          <line x1={w * f} y1={h * 0.9} x2={w * f} y2={h * 0.96} className="pl-leg" strokeWidth={2} />
          <rect x={w * f - w * 0.035} y={h * 0.955} width={w * 0.07} height={h * 0.045} rx={1.5} className="pl-foot" />
        </g>
      ))}
      <rect x={w * 0.05} y={h * 0.84} width={w * 0.9} height={h * 0.06} className="pl-steel" />
      {legs.map(([a, b, c, d]) => (
        <path key={a} d={`M${w * a} ${h * 0.6} L${w * b} ${h * 0.6} L${w * d} ${h * 0.845} L${w * c} ${h * 0.845} Z`}
          className="pl-teal" />
      ))}
      <path d={`M${w * 0.3} 0 L${w * 0.7} 0 L${w * 0.64} ${h * 0.22} L${w * 0.36} ${h * 0.22} Z`} className="pl-steel" />
      <Fins x={w * 0.34} y={0} w={w * 0.32} h={h * 0.2} n={4} vertical />
      <line x1={w * 0.8} y1={h * 0.24} x2={w * 0.91} y2={h * 0.1} className="pl-leg" strokeWidth={3} />
      <rect x={w * 0.01} y={h * 0.19} width={w * 0.98} height={h * 0.45} rx={Math.min(w, h) * 0.1} className="pl-teal" />
      <rect x={w * 0.14} y={h * 0.165} width={w * 0.72} height={h * 0.05} rx={2} className="pl-teal" />
      {[0.3, 0.7].map((f) => (
        <g key={f}>
          <circle cx={w * f} cy={ry} r={r} className="pl-rim" strokeWidth={1.5} />
          <circle cx={w * f} cy={ry} r={r * 0.8} className="pl-teal" />
          <Roll cx={w * f} cy={ry} r={r * 0.62} />
          <circle cx={w * f} cy={ry} r={r * 0.16} className="pl-part-r" />
        </g>
      ))}
      <RoundMotor cx={w * 0.92} cy={h * 0.09} r={Math.min(w, h) * 0.075} />
    </>
  );
}

/** Máy cán 2 trục nhìn thẳng (CC, kind crusher không khai dáng): phễu thép · thân teal · 2 trục cán lớn ·
 *  2 chân chữ A · mô-tơ tròn nhỏ cạnh trái. */
function RollCrusher({ w, h }: IconProps) {
  const top = h * 0.18, bot = h * 0.8, mid = (top + bot) / 2;
  const r = Math.min(w * 0.2, (bot - top) * 0.38);
  const leg = (a: number, b: number) =>
    `M${w * a} ${bot} L${w * b} ${bot} L${w * (b - 0.04)} ${h - 5} L${w * (a + 0.04)} ${h - 5} Z`;
  return (
    <>
      <path d={leg(0.1, 0.3)} className="pl-teal" />
      <path d={leg(0.7, 0.9)} className="pl-teal" />
      {[0.1, 0.7].map((f) => <rect key={f} x={w * f} y={h - 5} width={w * 0.2} height={5} rx={2}
        className="pl-foot" />)}
      <path d={`M${w * 0.2} 0 L${w * 0.8} 0 L${w * 0.88} ${top} L${w * 0.12} ${top} Z`} className="pl-steel" />
      <Fins x={w * 0.25} y={0} w={w * 0.5} h={top} n={4} vertical />
      <rect x={w * 0.03} y={top} width={w * 0.94} height={bot - top} rx={10} className="pl-teal" />
      <Roll cx={w / 2 - r * 1.1} cy={mid} r={r} />
      <Roll cx={w / 2 + r * 1.1} cy={mid} r={r} />
      <RoundMotor cx={w * 0.05} cy={bot - (bot - top) * 0.2} r={Math.min(w, h) * 0.085} />
    </>
  );
}

export function Crusher(p: IconProps) {
  if (p.variant === "mill") return <Mill {...p} />;
  if (p.variant === "creper") return <Creper {...p} />;
  return p.h > p.w * TALL_RATIO ? <Mill {...p} /> : <RollCrusher {...p} />;
}
