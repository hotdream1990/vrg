/* Dashboard — Giá mủ tư nhân (Mục 6 phiếu Báo giá mủ thị trường).
   Mỗi đơn vị tư nhân báo giá vào ngày khác nhau → lấy giá MỚI NHẤT của từng đơn vị trong cửa sổ ngày,
   ghi rõ ngày giá từng dòng. Kèm giá thành SVR 3L quy đổi và đối chiếu giá sàn nội địa SVR 3L với
   vùng hợp lý theo chuyên viên (giá thành tư nhân + 700.000–1.000.000 đồng/tấn). */

import { useEffect, useState } from "react";

import { dm, dmy } from "../../../lib/date";
import { getFloor, listFloors } from "../../../lib/floor-client";
import { type PrivateLatest, type PrivatePrice, fetchPrivateLatest } from "../../../lib/market-quote-client";
import { PRIVATE_SVR3L_COEF, svr3lCost } from "../../../lib/private-latex-cost";

type Floor = { price: number; title: string };

const vnum = (n: number, digits = 0) => n.toLocaleString("vi-VN", { maximumFractionDigits: digits });
const signed = (n: number, digits = 0) => `${n > 0 ? "+" : ""}${vnum(n, digits)}`;
/** Giá đại diện của 1 dòng: điểm giữa nếu là khoảng giá. */
const mid = (p?: PrivatePrice | null) => (p?.price == null ? null : (p.price + (p.price_max ?? p.price)) / 2);
const priceText = (p: PrivatePrice) =>
  p.price == null ? "—" : p.price_max != null ? `${vnum(p.price, 1)} – ${vnum(p.price_max, 1)}` : vnum(p.price, 1);
const isSvr3l = (grade: string) => grade.replace(/\s+/g, "").toUpperCase() === "SVR3L";
const upDown = (n: number) => ({ fontWeight: 600, color: n > 0 ? "#0b7a3b" : n < 0 ? "#c0392b" : "var(--muted)" });

export default function PrivateLatexPriceCard() {
  const [data, setData] = useState<PrivateLatest | null>(null);
  const [floor, setFloor] = useState<Floor | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchPrivateLatest().then(setData).catch((e) => setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu"));
    (async () => {
      try {
        const list = await listFloors();
        if (!list.length) return;
        const sch = await getFloor(list[0].lan);
        const item = sch.items.find((i) => isSvr3l(i.grade));
        if (item?.domestic_vnd) setFloor({ price: item.domestic_vnd, title: sch.title?.trim() || `lần ${sch.lan}` });
      } catch { /* không có giá sàn thì chỉ ẩn phần so sánh */ }
    })();
  }, []);

  const rows = [...(data?.rows ?? [])].sort((a, b) => a.name.localeCompare(b.name, "vi"));
  const ready = rows.length > 0;
  const coef = String(PRIVATE_SVR3L_COEF).replace(".", ",");
  const costs = rows.map((r) => svr3lCost(mid(r), r.processing_cost)).filter((v): v is number => v != null);
  const ref = costs.length ? Math.round(costs.reduce((a, b) => a + b, 0) / costs.length) : null;
  const band = ref != null && data ? [ref + data.rule.floor_premium_min, ref + data.rule.floor_premium_max] : null;
  const floorVsBand = floor && band
    ? floor.price < band[0] ? { text: `thấp hơn vùng ${vnum(band[0] - floor.price)}`, warn: true }
      : floor.price > band[1] ? { text: `cao hơn vùng ${vnum(floor.price - band[1])}`, warn: true }
        : { text: "nằm trong vùng", warn: false }
    : null;

  return (
    <div className="card" id="sec-tunhan" style={{ marginBottom: 16 }}>
      <div className="card-head">
        <div>
          <h3 className={ready ? undefined : "title-demo"}>Giá mủ tư nhân</h3>
          {ready && (
            <div className="sub">
              Giá mới nhất của từng đơn vị trong {data!.window_days} ngày · giá mủ đồng/độ TSC · giá thành SVR 3L
              = giá × {coef} × 100.000 + chi phí gia công chế biến
            </div>
          )}
        </div>
        <span className={`chip ${ready ? "" : "demo"}`}>{ready ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
      </div>
      {err ? (
        <div className="scan-empty">Không tải được giá mủ tư nhân: {err}</div>
      ) : data == null ? (
        <div className="scan-empty">Đang tải…</div>
      ) : !ready ? (
        <div className="scan-empty">Chưa có giá mủ tư nhân trong {data.window_days} ngày gần nhất.</div>
      ) : (
        <>
          {band && (
            <div className="private-band">
              <span>Giá thành tham chiếu (trung bình {costs.length} đơn vị): <b>{vnum(ref!)}</b></span>
              <span>Vùng giá sàn hợp lý (+{vnum(data.rule.floor_premium_min)} – {vnum(data.rule.floor_premium_max)}):{" "}
                <b>{vnum(band[0])} – {vnum(band[1])}</b></span>
              {floor && floorVsBand && (
                <span>Giá sàn nội địa SVR 3L {floor.title}: <b>{vnum(floor.price)}</b>{" "}
                  <span className={`chip ${floorVsBand.warn ? "warn" : ""}`}>{floorVsBand.text}</span></span>
              )}
            </div>
          )}
          <table>
            <thead>
              <tr>
                <th>Đơn vị tư nhân</th>
                <th>Ngày giá</th>
                <th className="r">Giá mủ (đồng/độ TSC)</th>
                <th className="r">So với lần báo trước</th>
                <th className="r">Giá thành SVR 3L (đồng/tấn)</th>
                {floor && <th className="r">Giá sàn VRG − giá thành</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const now = mid(r);
                const before = mid(r.prev);
                const delta = now != null && before != null ? now - before : null;
                const lo = svr3lCost(r.price, r.processing_cost);
                const hi = r.price_max != null ? svr3lCost(r.price_max, r.processing_cost) : null;
                const costMid = svr3lCost(now, r.processing_cost);
                const gap = floor && costMid != null ? floor.price - costMid : null;
                return (
                  <tr key={r.name}>
                    <td style={{ fontWeight: 500 }}>{r.name}</td>
                    <td>{dm(r.as_of)}</td>
                    <td className="r">{priceText(r)}</td>
                    <td className="r" style={delta == null ? { color: "var(--muted)" } : upDown(delta)}
                      title={r.prev ? `Lần trước ${dmy(r.prev.as_of)}: ${priceText(r.prev)}` : "Chưa có lần báo trước trong cửa sổ"}>
                      {delta == null ? "—" : `${signed(delta, 1)} (${signed((delta / before!) * 100, 1)}%)`}
                    </td>
                    <td className="r" style={{ fontWeight: 600 }}>
                      {lo == null ? "—" : hi != null ? `${vnum(lo)} – ${vnum(hi)}` : vnum(lo)}
                    </td>
                    {floor && (
                      <td className="r" style={gap == null ? undefined : upDown(gap)}>
                        {gap == null ? "—" : `${signed(gap)} (${signed((gap / costMid!) * 100, 1)}%)`}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}
      <p style={{ color: "var(--muted)", fontSize: 11, margin: "12px 0 0" }}>
        Khoảng giá (vd 560 – 563) tính theo điểm giữa. Vùng giá sàn hợp lý theo ý kiến chuyên viên Ban TTKD.
        Nhập ở Báo giá mủ thị trường › Mục 6.
      </p>
    </div>
  );
}
