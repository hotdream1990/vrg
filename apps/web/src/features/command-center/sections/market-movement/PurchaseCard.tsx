import { Segmented } from "antd";
import { useEffect, useState } from "react";

import { dm } from "../../../../lib/date";
import {
  type Material, type PriceBasket, type PurchaseSeries, type PurchaseVolumeSeries,
  fetchPurchaseSeries, fetchPurchaseVolume,
} from "../../../../lib/series-client";
import { readAt, thinNote } from "../../../../lib/purchase-series";
import PriceVolumeChart from "../../charts/PriceVolumeChart";
import StackedDaysChart from "../../charts/StackedDaysChart";

const vnum = (n: number, d = 0) => n.toLocaleString("vi-VN", { maximumFractionDigits: d });

export type Kind = { key: Material; title: string; unit: string; color: string };

type View = "price" | "region" | "company";

const VIEWS: { value: View; label: string }[] = [
  { value: "price", label: "Giá & sản lượng" },
  { value: "region", label: "Theo khu vực" },
  { value: "company", label: "Theo đơn vị" },
];

const BASKETS: { value: PriceBasket; label: string }[] = [
  { value: "steady", label: "Đơn vị khai đều" },
  { value: "all", label: "Tất cả đơn vị" },
];

function priceCaption(rows: PurchaseSeries["rows"], k: Kind): string {
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

function volumeCaption(vol: PurchaseVolumeSeries, view: View): string {
  const last = vol.rows.at(-1);
  if (!last) return "";
  const top = Object.entries(last.values).sort((a, b) => b[1] - a[1]).slice(0, 3)
    .map(([key, v]) => `${key} ${vnum(v, 1)}`).join(", ");
  const what = view === "region" ? "khu vực" : "đơn vị";
  return `Ngày ${dm(last.as_of)}: ${vnum(last.total ?? 0, 1)} tấn — ${what} mua nhiều nhất: ${top} tấn.`;
}

/** Một loại mủ nguyên liệu: đơn giá + sản lượng theo ngày, hoặc sản lượng chia theo khu vực/đơn vị. */
export default function PurchaseCard({ kind, from }: { kind: Kind; from: string }) {
  const [view, setView] = useState<View>("price");
  const [basket, setBasket] = useState<PriceBasket>("steady");
  const [price, setPrice] = useState<PurchaseSeries | null>(null);
  const [vol, setVol] = useState<PurchaseVolumeSeries | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    const fail = (e: unknown) => setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu");
    if (view === "price") {
      setPrice(null);
      fetchPurchaseSeries(from, undefined, basket).then(setPrice).catch(fail);
    } else {
      setVol(null);
      fetchPurchaseVolume(kind.key, view, from).then(setVol).catch(fail);
    }
  }, [view, basket, kind.key, from]);

  const rows = price?.rows ?? [];
  const loading = view === "price" ? !price : !vol;
  const ready = view === "price"
    ? rows.some((r) => r[kind.key].units > 0 || r[kind.key].qty != null)
    : !!vol?.rows.length;

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3 className={ready ? undefined : "title-demo"}>{kind.title}</h3>
          <div className="sub">
            {view === "price" ? (price ? priceCaption(rows, kind) : "")
              : (vol ? volumeCaption(vol, view) : "")}
          </div>
        </div>
        <span className={`chip ${ready ? "" : "demo"}`}>{ready ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
      </div>

      {/* Nút chọn để riêng một hàng: card nằm nửa màn hình, nhét cạnh tiêu đề là vỡ chữ. */}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
        {view === "price" && (
          <Segmented size="small" value={basket} options={BASKETS}
                     onChange={(v) => setBasket(v as PriceBasket)} />
        )}
        <Segmented size="small" value={view} options={VIEWS} onChange={(v) => setView(v as View)} />
      </div>

      {err ? <div className="scan-empty">{err}</div>
        : loading ? <div className="scan-empty">Đang tải…</div>
        : !ready ? <div className="scan-empty">Đơn vị thành viên chưa khai loại mủ này.</div>
        : view === "price" ? (
          <div className="chart-wrap">
            <PriceVolumeChart
              labels={rows.map((r) => dm(r.as_of))}
              min={rows.map((r) => r[kind.key].min)}
              max={rows.map((r) => r[kind.key].max)}
              avg={rows.map((r) => r[kind.key].avg)}
              qty={rows.map((r) => r[kind.key].qty)}
              color={kind.color}
              unit={kind.unit}
            />
          </div>
        ) : (
          <div className="chart-wrap">
            <StackedDaysChart rows={vol!.rows} series={vol!.series} digits={1}
                              footer={(r) => `Tổng ngày: ${vnum(r.total ?? 0, 1)} tấn`} />
          </div>
        )}

      <p style={{ color: "var(--muted)", fontSize: 11, margin: "10px 0 0" }}>
        Số liệu do đơn vị thành viên tự khai (biểu Thu mua + giá mủ nguyên liệu của đơn vị); ngày không
        có số hoặc bằng 0 được bỏ qua.{" "}
        {view === "price"
          ? `Cột sản lượng (trục phải) luôn là tổng của mọi đơn vị. Dải giá ${basket === "steady"
              ? `chỉ tính ${price?.basket_units[kind.key] ?? 0} đơn vị khai đều — các ngày mới so được với nhau`
              : "tính trên mọi đơn vị có khai — đáy/đỉnh nhảy theo việc hôm đó ai nộp"}.`
          : "Mỗi cột là sản lượng mua trong đúng ngày đó (không cộng dồn)."}
      </p>
    </div>
  );
}
