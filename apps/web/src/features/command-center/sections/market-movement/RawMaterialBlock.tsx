import { Segmented } from "antd";
import { useEffect, useState } from "react";

import { type PriceBasket, type PurchaseSeries, fetchPurchaseSeries } from "../../../../lib/api-client";
import { dm } from "../../../../lib/date";
import { CUP_PRICE_UNIT_SHORT, LATEX_PRICE_UNIT_SHORT } from "../../../../lib/purchase-price-unit";
import { readAt, thinNote } from "../../../../lib/purchase-series";
import PriceVolumeChart from "../../charts/PriceVolumeChart";

const vnum = (n: number, d = 0) => n.toLocaleString("vi-VN", { maximumFractionDigits: d });
const WINDOW_DAYS = 30;   // cửa sổ hiển thị gần nhất cho dễ đọc

type Kind = { key: "latex" | "cup"; title: string; unit: string; color: string };

/** Hai loại mủ nguyên liệu đơn vị thành viên thu mua — cùng một khuôn card. */
const KINDS: Kind[] = [
  { key: "latex", title: "Giá & sản lượng mủ nước (thu mua nội địa)", unit: LATEX_PRICE_UNIT_SHORT, color: "#16AF67" },
  { key: "cup", title: "Giá & sản lượng mủ chén (thu mua nội địa)", unit: CUP_PRICE_UNIT_SHORT, color: "#a855f7" },
];

const BASKETS: { value: PriceBasket; label: string }[] = [
  { value: "steady", label: "Đơn vị khai đều" },
  { value: "all", label: "Tất cả đơn vị" },
];

const from = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() - (days - 1));
  return d.toISOString().slice(0, 10);
};

function caption(rows: PurchaseSeries["rows"], k: Kind): string {
  // Mốc đọc = ngày gần nhất ĐỦ ĐƠN VỊ khai; ngày mới hơn (nếu có) được nhắc riêng, không lẫn vào số.
  const { settled, thin } = readAt(rows, k.key);
  if (!settled) return "";
  const s = settled[k.key];
  const price = s.units
    ? `${vnum(s.min!)}–${vnum(s.max!)} ${k.unit} · TB ${vnum(s.avg!)} · ${s.units} đơn vị`
    : "chưa có đơn giá";
  const qty = s.qty != null ? ` · sản lượng ${vnum(s.qty, 1)} tấn (${s.qty_units} đơn vị)` : "";
  return `Ngày ${dm(settled.as_of)}: ${price}${qty}.${thinNote(thin, k.key, dm)}`;
}

/** Giá & sản lượng thu mua mủ nguyên liệu — CÙNG một nguồn: số đơn vị thành viên tự khai.
 *  Cột = sản lượng thu mua trong ngày, dải + đường = khoảng đơn giá giữa các đơn vị.
 *  Ô trống và giá trị 0 bị bỏ qua (không vẽ) để chuỗi không giật vì hôm có hôm không. */
export default function RawMaterialBlock() {
  const [basket, setBasket] = useState<PriceBasket>("steady");
  const [series, setSeries] = useState<PurchaseSeries | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setSeries(null);
    fetchPurchaseSeries(from(WINDOW_DAYS), undefined, basket)
      .then(setSeries)
      .catch((e) => setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu"));
  }, [basket]);

  return (
    <div className="grid-2">
      {KINDS.map((k) => {
        const rows = series?.rows ?? [];
        const ready = rows.some((r) => r[k.key].units > 0 || r[k.key].qty != null);
        return (
          <div className="card" key={k.key}>
            <div className="card-head">
              <div>
                <h3 className={ready ? undefined : "title-demo"}>{k.title}</h3>
                {series && <div className="sub">{caption(rows, k)}</div>}
              </div>
              <span className={`chip ${ready ? "" : "demo"}`}>{ready ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
            </div>
            {err ? <div className="scan-empty">{err}</div>
              : !series ? <div className="scan-empty">Đang tải…</div>
              : !ready ? <div className="scan-empty">Đơn vị thành viên chưa khai giá/sản lượng loại mủ này.</div>
              : (
                <>
                  {/* Nút chọn rổ để riêng một hàng: card nằm nửa màn hình, nhét vào cạnh tiêu đề là vỡ chữ. */}
                  <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
                    <Segmented size="small" value={basket} options={BASKETS}
                               onChange={(v) => setBasket(v as PriceBasket)} />
                  </div>
                  <div className="chart-wrap">
                    <PriceVolumeChart
                      labels={rows.map((r) => dm(r.as_of))}
                      min={rows.map((r) => r[k.key].min)}
                      max={rows.map((r) => r[k.key].max)}
                      avg={rows.map((r) => r[k.key].avg)}
                      qty={rows.map((r) => r[k.key].qty)}
                      color={k.color}
                      unit={k.unit}
                    />
                  </div>
                  <p style={{ color: "var(--muted)", fontSize: 11, margin: "10px 0 0" }}>
                    Số liệu do đơn vị thành viên tự khai (biểu Thu mua + giá mủ nguyên liệu của đơn vị);
                    ngày không có số hoặc bằng 0 được bỏ qua. Cột sản lượng (trục phải) luôn là tổng
                    của mọi đơn vị. Dải giá {basket === "steady"
                      ? `chỉ tính ${series.basket_units[k.key]} đơn vị khai đều — các ngày mới so được với nhau`
                      : "tính trên mọi đơn vị có khai — đáy/đỉnh nhảy theo việc hôm đó ai nộp"}.
                  </p>
                </>
              )}
          </div>
        );
      })}
    </div>
  );
}
