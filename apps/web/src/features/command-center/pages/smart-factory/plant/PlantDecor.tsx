/* Nét trang trí của khu (vẽ dưới cùng): basin = máng inox (mương đánh đông, bệ, lòng hầm sấy) · pipe =
   ống thép theo `points` · arrow_text = đường ống nhỏ + đầu mũi tên rỗng ở ĐIỂM CUỐI, xoay theo hướng đoạn
   cuối (chỉ trái/phải/lên/xuống đều được) + chữ đậm (`text_xy` có thì neo trái đúng đó, giữa theo chiều dọc)
   · badge = ô chữ nhỏ nền trắng viền đậm (vd "pID" cạnh máy cán), (x, y) = góc trên-trái. */

import type { PlantDecor } from "../../../../../lib/smart-factory-client";

/** arrow_text không có `points` → mũi tên ngang dài `w` (hoặc mức này) tính từ (x, y). */
const ARROW_LEN = 40;
const TEXT_GAP = 8;
/** Đầu mũi tên: dài × rộng (đơn vị khung khu). */
const HEAD_L = 18;
const HEAD_W = 16;
/** Khoảng cách sườn dọc của máng · cao chân đỡ. */
const RIB_GAP = 70;
const FOOT_H = 8;
/** Ô badge: cao · lề ngang · bề rộng ước theo số ký tự (chữ đậm 13). */
const BADGE_H = 20;
const BADGE_PAD = 5;
const BADGE_CHAR_W = 8;

type Pt = [number, number];

const toPoints = (p: Pt[]) => p.map(([x, y]) => `${x},${y}`).join(" ");
const range = (n: number) => Array.from({ length: n }, (_, i) => i);

function ArrowText({ d }: { d: PlantDecor }) {
  const x = d.x ?? 0;
  const y = d.y ?? 0;
  const line: Pt[] = d.points && d.points.length >= 2 ? d.points : [[x, y], [x + (d.w || ARROW_LEN), y]];
  const [ex, ey] = line[line.length - 1];
  const [px, py] = line[line.length - 2];
  const dx = ex - px;
  const dy = ey - py;
  const len = Math.hypot(dx, dy) || 1;
  const deg = (Math.atan2(dy, dx) * 180) / Math.PI;
  // Ống dừng ở chân đầu mũi tên (đầu rỗng — ống không xuyên qua).
  const shaft: Pt[] = [...line.slice(0, -1), [ex - (dx / len) * HEAD_L, ey - (dy / len) * HEAD_L]];
  // Không khai `text_xy`: chữ nối tiếp theo hướng đoạn cuối — ngang → sau đầu mũi; dọc → dưới/trên đầu mũi.
  const horiz = Math.abs(dx) >= Math.abs(dy);
  const anchor = d.text_xy ? "start" : horiz ? (dx >= 0 ? "start" : "end") : "middle";
  const [tx, ty] = d.text_xy
    ?? (horiz ? [ex + (dx >= 0 ? TEXT_GAP : -TEXT_GAP), ey] : [ex, ey + (dy >= 0 ? 18 : -TEXT_GAP - 6)]);
  return (
    <g>
      <polyline points={toPoints(shaft)} className="pl-arrow" />
      <polyline points={toPoints(shaft)} className="pl-arrow-core" />
      <path d={`M0 0 L${-HEAD_L} ${-HEAD_W / 2} L${-HEAD_L} ${HEAD_W / 2} Z`} className="pl-arrow-head"
        transform={`translate(${ex} ${ey}) rotate(${deg})`} />
      {d.text && (
        <text x={tx} y={ty} textAnchor={anchor} dominantBaseline="central" className="pl-arrow-text">{d.text}</text>
      )}
    </g>
  );
}

/** Máng inox: thân gradient dọc · mép trên sáng · sườn dọc mảnh + thanh giằng giữa · chân đỡ. */
function Basin({ d }: { d: PlantDecor }) {
  const x = d.x ?? 0;
  const y = d.y ?? 0;
  const w = d.w ?? 0;
  const h = d.h ?? 0;
  const n = Math.max(1, Math.round(w / RIB_GAP));
  const ribX = (i: number) => x + (w * i) / n;
  return (
    <g>
      {range(n + 1).map((i) => (
        <rect key={`f${i}`} x={ribX(i) - 3} y={y + h} width={6} height={FOOT_H} className="pl-basin-foot" />
      ))}
      <rect x={x} y={y} width={w} height={h} rx={3} className="pl-basin" />
      <line x1={x + 2} y1={y + h * 0.55} x2={x + w - 2} y2={y + h * 0.55} className="pl-basin-rib" />
      {range(n - 1).map((i) => (
        <line key={`r${i}`} x1={ribX(i + 1)} y1={y + 4} x2={ribX(i + 1)} y2={y + h - 3} className="pl-basin-rib" />
      ))}
      <line x1={x + 2} y1={y + 2.5} x2={x + w - 2} y2={y + 2.5} className="pl-basin-lip" />
    </g>
  );
}

function Badge({ d }: { d: PlantDecor }) {
  const text = d.text ?? "";
  const w = text.length * BADGE_CHAR_W + 2 * BADGE_PAD;
  return (
    <g transform={`translate(${d.x ?? 0} ${d.y ?? 0})`} className="pl-badge">
      <rect width={w} height={BADGE_H} rx={2} />
      <text x={w / 2} y={BADGE_H / 2} textAnchor="middle" dominantBaseline="central">{text}</text>
    </g>
  );
}

export function PlantDecorShape({ d }: { d: PlantDecor }) {
  switch (d.kind) {
    case "basin":
      return <Basin d={d} />;
    case "pipe":
      // Ống tròn: nét đậm xám + nét mảnh sáng ở giữa.
      return d.points && d.points.length >= 2 ? (
        <g>
          <polyline points={toPoints(d.points)} className="pl-pipe" />
          <polyline points={toPoints(d.points)} className="pl-pipe-shine" />
        </g>
      ) : null;
    case "arrow_text":
      return <ArrowText d={d} />;
    case "badge":
      return d.text ? <Badge d={d} /> : null;
    default:
      return null;
  }
}
