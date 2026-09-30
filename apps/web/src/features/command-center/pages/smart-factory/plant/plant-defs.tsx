/* <defs> dùng chung của khung sơ đồ — khai MỘT lần mỗi SVG, mọi thiết bị tái dùng qua id (CSS
   `fill: url(#…)` trong plant-devices.css). Gradient theo khung của chính hình (objectBoundingBox) nên
   hình to/nhỏ/xoay đều đúng. Chỉ một sơ đồ trên trang → id cố định không trùng. */

type Stop = [number, string];

/** Gradient dọc (trên → dưới) hoặc ngang (trái → phải). */
function Linear({ id, stops, across = false }: { id: string; stops: Stop[]; across?: boolean }) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2={across ? "1" : "0"} y2={across ? "0" : "1"}>
      {stops.map(([o, c]) => <stop key={o} offset={o} stopColor={c} />)}
    </linearGradient>
  );
}

/** Gradient tròn, điểm sáng lệch trên-trái → khối tròn nổi. */
function Radial({ id, stops }: { id: string; stops: Stop[] }) {
  return (
    <radialGradient id={id} cx="0.38" cy="0.34" r="0.72">
      {stops.map(([o, c]) => <stop key={o} offset={o} stopColor={c} />)}
    </radialGradient>
  );
}

export function PlantDefs() {
  return (
    <defs>
      {/* Máng inox: sáng ở mép trên → xám đậm ở đáy. */}
      <Linear id="pl-g-basin" stops={[[0, "#f5f7f9"], [0.5, "#cfd4da"], [1, "#9ba3ac"]]} />
      <Linear id="pl-g-steel" stops={[[0, "#eef1f4"], [0.55, "#bcc3cb"], [1, "#8e97a1"]]} />
      {/* Thành bể / trụ thép nhìn ngang: tối 2 mép, sáng giữa. */}
      <Linear id="pl-g-steel-h" across
        stops={[[0, "#9aa3ac"], [0.3, "#eef1f4"], [0.7, "#c5cbd2"], [1, "#8e97a1"]]} />
      {/* Thân máy teal đậm như RELCO; bản `-h` cho phễu trụ (sáng dọc giữa). */}
      <Linear id="pl-g-teal" stops={[[0, "#1d6269"], [1, "#083c42"]]} />
      <Linear id="pl-g-teal-h" across
        stops={[[0, "#062f34"], [0.35, "#1f6d74"], [0.6, "#185a61"], [1, "#052a2f"]]} />
      {/* Đang chạy: xanh lá tươi kiểu neon như RELCO (không phải xanh VRG nhạt). */}
      <Linear id="pl-g-run" stops={[[0, "#6dff5c"], [0.45, "#39f02a"], [1, "#1fc41f"]]} />
      <Linear id="pl-g-idle" stops={[[0, "#e4e8ec"], [1, "#a3acb6"]]} />
      <Radial id="pl-g-run-r" stops={[[0, "#a4ff96"], [0.5, "#39f02a"], [1, "#12a312"]]} />
      <Radial id="pl-g-idle-r" stops={[[0, "#f3f5f7"], [0.6, "#b4bcc5"], [1, "#7c8691"]]} />
    </defs>
  );
}
