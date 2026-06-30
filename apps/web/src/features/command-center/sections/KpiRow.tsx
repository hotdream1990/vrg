import { useEffect, useState } from "react";

import {
  type PriceSheet,
  type PurchaseSheet,
  fetchPurchaseSheet,
  fetchSheet,
} from "../../../lib/api-client";

type Delta = "up" | "down" | "flat";
type Card = { label: string; value: string; delta: Delta; deltaText: string; sub: string; demo?: boolean };

const vnum = (n: number, d = 0) => n.toLocaleString("vi-VN", { maximumFractionDigits: d });
const ddmm = (iso: string) => { const [, m, d] = iso.split("-"); return `${d}/${m}`; };

const deltaOf = (cur: number, prev: number | null): Pick<Card, "delta" | "deltaText"> => {
  if (prev == null || !prev) return { delta: "flat", deltaText: "≈ Mới" };
  const pct = ((cur - prev) / prev) * 100;
  const delta: Delta = pct > 0.05 ? "up" : pct < -0.05 ? "down" : "flat";
  const arrow = delta === "up" ? "▲" : delta === "down" ? "▼" : "≈";
  return { delta, deltaText: `${arrow} ${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%` };
};

/** Chuỗi USD/T (ngày tăng dần, bỏ ô trống) cho 1 (sàn, grade) từ bảng tính giá. */
function usdSeries(sheet: PriceSheet, exchange: string, grade: string): { date: string; usd: number }[] {
  const g = sheet.groups.find((x) => x.exchange.toUpperCase() === exchange.toUpperCase());
  const col = g?.cols.find((c) => c.grade.toUpperCase() === grade.toUpperCase());
  if (!col) return [];
  return [...sheet.rows]
    .sort((a, b) => a.as_of.localeCompare(b.as_of))
    .map((r) => ({ date: r.as_of, usd: r.cells[col.key]?.usd ?? null }))
    .filter((p): p is { date: string; usd: number } => p.usd != null);
}

function priceCard(label: string, s: { date: string; usd: number }[]): Card {
  if (s.length === 0)
    return { label, value: "—", delta: "flat", deltaText: "Chưa có dữ liệu", sub: "Chưa quét giá", demo: true };
  const cur = s[s.length - 1];
  const prev = s.length >= 2 ? s[s.length - 2].usd : null;
  return { label, value: vnum(cur.usd), ...deltaOf(cur.usd, prev), sub: `Cập nhật ${ddmm(cur.date)}` };
}

function purchaseCard(p: PurchaseSheet): Card {
  const label = "Mủ nước (VNĐ/độ TSC)";
  const empty: Card = { label, value: "—", delta: "flat", deltaText: "Chưa có dữ liệu", sub: "Chưa nhập giá", demo: true };
  if (!p.dates.length || !p.companies.length) return empty;
  const avg = (d: string) => {
    const a = p.companies.map((c) => p.values[c]?.[d]).filter((v): v is number => v != null);
    return a.length ? a.reduce((s, x) => s + x, 0) / a.length : null;
  };
  const latest = p.dates[0]; // mới nhất trước
  const vals = p.companies.map((c) => p.values[c]?.[latest]).filter((v): v is number => v != null);
  if (!vals.length) return empty;
  const min = Math.min(...vals), max = Math.max(...vals);
  const value = min === max ? vnum(min) : `${vnum(min)}–${vnum(max)}`;
  return { label, value, ...deltaOf(avg(latest)!, p.dates[1] ? avg(p.dates[1]) : null), sub: `Thu mua nội địa ${ddmm(latest)}` };
}

const LOADING: Card[] = ["RSS3 · OSE", "SMR20 · MRB", "Latex · MRB", "Mủ nước"].map((l) => ({
  label: l, value: "…", delta: "flat", deltaText: "Đang tải", sub: "",
}));

/** Hàng 4 thẻ KPI giá chủ lực — dữ liệu THẬT từ DB (giá USD/T + Δ + ngày); thiếu data → cam. */
export default function KpiRow() {
  const [cards, setCards] = useState<Card[]>(LOADING);

  useEffect(() => {
    Promise.all([fetchSheet({ days: 30 }), fetchPurchaseSheet()])
      .then(([sheet, purchase]) => setCards([
        priceCard("RSS3 · OSE (USD/tấn)", usdSeries(sheet, "OSE", "RSS3")),
        priceCard("SMR20 · MRB (USD/tấn)", usdSeries(sheet, "MRB", "SMR20")),
        priceCard("Latex · MRB (USD/tấn)", usdSeries(sheet, "MRB", "LATEX")),
        purchaseCard(purchase),
      ]))
      .catch((e) => {
        console.error("[KpiRow] Lỗi tải KPI giá:", e);
        const sub = e instanceof Error ? e.message : "Lỗi tải dữ liệu";
        setCards(LOADING.map((c) => ({ ...c, value: "—", deltaText: "Lỗi tải", sub, demo: true })));
      });
  }, []);

  return (
    <div className="kpi-row">
      {cards.map((k) => (
        <div className={`kpi${k.demo ? " kpi-demo" : ""}`} key={k.label}>
          <div className="label">{k.label}</div>
          <div className="value">{k.value}</div>
          <span className={`delta ${k.delta}`}>{k.deltaText}</span>
          <div className="sub">{k.sub}</div>
        </div>
      ))}
    </div>
  );
}
