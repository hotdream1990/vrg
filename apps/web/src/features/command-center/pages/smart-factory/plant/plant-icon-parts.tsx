/* Chi tiết dùng chung khi vẽ biểu tượng thiết bị (plant-icons*.tsx). Màu KHÔNG ghi ở đây mà theo class
   (plant-devices.css): `pl-part*` = bộ phận xanh khi chạy / xám thép khi dừng; còn lại là thép · teal cố định. */

import type { ReactNode } from "react";

/** Khung cục bộ (0,0)–(w,h) của thiết bị; `angle` = góc xoay của cả thiết bị (độ); `variant` = dáng máy
 *  (máy cán: "mill" tháp cán · "creper" máy 2 trục). */
export type IconProps = { w: number; h: number; angle: number; variant?: string };

export const range = (n: number) => Array.from({ length: n }, (_, i) => i);

/** Hướng "xuống đất" của THẾ GIỚI trong khung cục bộ đã xoay `angle` độ → chân đỡ luôn thẳng đứng. */
export function downDir(angle: number): [number, number] {
  const a = (angle * Math.PI) / 180;
  return [Math.sin(a), Math.cos(a)];
}

/** Nhóm QUAY quanh (cx, cy) khi thiết bị chạy (CSS `.pl-spin`). Hình bên trong vẽ quanh gốc (0,0);
 *  vòng tròn ẩn bán kính `r` giữ khung bao đối xứng → tâm quay đúng tâm. */
export function Spin({ cx, cy, r, children }: { cx: number; cy: number; r: number; children: ReactNode }) {
  return (
    <g transform={`translate(${cx} ${cy})`}>
      <g className="pl-spin">
        <circle r={r} fill="none" stroke="none" />
        {children}
      </g>
    </g>
  );
}

/** Motor tròn (nhìn đầu trục): thân xanh/xám + tâm đậm. */
export function RoundMotor({ cx, cy, r }: { cx: number; cy: number; r: number }) {
  return (
    <>
      <circle cx={cx} cy={cy} r={r} className="pl-part-r" />
      <circle cx={cx} cy={cy} r={r * 0.32} className="pl-hub" />
    </>
  );
}

/** Gân tản nhiệt: `n` nét song song chia đều hình chữ nhật (dọc nếu `vertical`). */
export function Fins({ x, y, w, h, n, vertical = false }: {
  x: number; y: number; w: number; h: number; n: number; vertical?: boolean;
}) {
  return (
    <>
      {range(n).map((i) => {
        const f = (i + 1) / (n + 1);
        return vertical
          ? <line key={i} x1={x + w * f} y1={y + 2} x2={x + w * f} y2={y + h - 2} className="pl-fin" />
          : <line key={i} x1={x + 2} y1={y + h * f} x2={x + w - 2} y2={y + h * f} className="pl-fin" />;
      })}
    </>
  );
}

/** Trục cán: vành xám đậm + mặt sáng có chữ thập (quay khi chạy) + tâm. */
export function Roll({ cx, cy, r }: { cx: number; cy: number; r: number }) {
  const s = r * 0.5;
  return (
    <>
      <circle cx={cx} cy={cy} r={r} className="pl-rim" strokeWidth={r * 0.16} />
      <Spin cx={cx} cy={cy} r={r * 0.66}>
        <circle r={r * 0.62} className="pl-roll-face" />
        <line x1={-s} y1={0} x2={s} y2={0} className="pl-roll-spoke" />
        <line x1={0} y1={-s} x2={0} y2={s} className="pl-roll-spoke" />
        <circle r={r * 0.2} className="pl-hub" />
      </Spin>
    </>
  );
}
