/* Gom tóm tắt số liệu 6 nhóm (đã tính xu hướng/%thay đổi) → gửi AI nhận định.
   Dùng lại các endpoint sẵn có; nhóm nào lỗi/thiếu data → ghi "Chưa đủ dữ liệu". */

import {
  type PriceSheet,
  fetchPhysicalSheet,
  fetchPurchaseSheet,
  fetchSheet,
} from "../../../../lib/api-client";
import { dm, dmy } from "../../../../lib/date";
import { compareFloorVsMarket } from "../../../../lib/floor-vs-market";
import { getFloor, listFloors } from "../../../../lib/floor-client";
import { fetchInventory } from "../../../../lib/inventory-client";
import type { GroupMeta } from "../../../../lib/market-movement-client";
import { type MarketQuote, getQuote, listQuotes } from "../../../../lib/market-quote-client";
import { isNoTrading } from "../../../../lib/no-trading";
import { CUP_PRICE_UNIT_SHORT } from "../../../../lib/purchase-price-unit";

const vnum = (n: number, d = 0) => n.toLocaleString("vi-VN", { maximumFractionDigits: d });

/** Mốc AI THỰC SỰ đối chiếu: phiên/kỳ mới nhất (so kỳ liền trước). Nhận định chỉ dùng 2 mốc này —
 *  KHÔNG phân tích cả kho lịch sử — nên nhãn phải phản ánh đúng, tránh ghi "N phiên" gây hiểu nhầm. */
function usedRange(isos: (string | null | undefined)[], noun = "phiên"): string {
  const s = [...new Set(isos.filter((x): x is string => !!x))].sort();
  if (!s.length) return "—";
  const cur = dmy(s.at(-1)!);
  return s.length >= 2 ? `${noun} ${cur} (so ${dm(s.at(-2)!)})` : `${noun} ${cur}`;
}
const latestOf = (isos: (string | null | undefined)[]): string | null => {
  const s = [...new Set(isos.filter((x): x is string => !!x))].sort();
  return s.length ? s.at(-1)! : null;
};
const hasData = (summary: string) => !summary.startsWith("Chưa đủ dữ liệu");
const pct = (cur: number, prev: number | null | undefined) =>
  prev == null || !prev ? "" : ` (${(cur - prev) / prev >= 0 ? "+" : ""}${(((cur - prev) / prev) * 100).toFixed(2)}%)`;

/** Chuỗi USD/T của 1 sàn·mặt hàng. BỎ phiên giá 0 (No Trading — sàn nghỉ/không ra settlement):
 *  không phải một mức giá, để lọt vào sẽ báo cho AI là "0 USD/T (-100%)". */
function usdSeries(sheet: PriceSheet, ex: string, grade: string): number[] {
  const col = sheet.groups.find((g) => g.exchange.toUpperCase() === ex.toUpperCase())
    ?.cols.find((c) => c.grade.toUpperCase() === grade.toUpperCase());
  if (!col) return [];
  return [...sheet.rows].sort((a, b) => a.as_of.localeCompare(b.as_of))
    .map((r) => r.cells[col!.key]?.usd)
    .filter((v): v is number => v != null && !isNoTrading(v));
}
function fxSeries(sheet: PriceSheet, pair: string): number[] {
  return [...sheet.rows].sort((a, b) => a.as_of.localeCompare(b.as_of))
    .map((r) => r.fx?.[pair]).filter((v): v is number => v != null);
}
const EXCHANGES: [string, string, string][] = [
  ["OSE", "RSS3", "OSE RSS3"], ["OSE", "TSR20", "OSE TSR20"],
  ["SHANGHAI", "RSS3", "SHFE RSS3"], ["SGX", "TSR20", "SGX TSR20"], ["SGX", "RSS3", "SGX RSS3"],
];
const FX_SHOW: [string, string][] = [
  ["USD/VND (Bán)", "USD/VND"], ["USD/MYR", "USD/MYR"], ["USD/JPY", "USD/JPY"], ["USD/CNY", "USD/CNY"],
];

function exchangeLines(sheet: PriceSheet): string {
  const out = EXCHANGES.map(([ex, gr, label]) => {
    const s = usdSeries(sheet, ex, gr);
    if (!s.length) return null;
    return `${label}: ${vnum(s.at(-1)!)} USD/T${pct(s.at(-1)!, s.at(-2))}`;
  }).filter(Boolean);
  return out.length ? out.join("; ") : "Chưa đủ dữ liệu.";
}
function fxLines(sheet: PriceSheet): string {
  const out = FX_SHOW.map(([pair, label]) => {
    const s = fxSeries(sheet, pair);
    if (!s.length) return null;
    const d = label === "USD/VND" ? 0 : 2; // VND số nguyên; MYR/JPY/CNY 2 số lẻ (tránh MYR hiện "4")
    return `${label}: ${vnum(s.at(-1)!, d)}${pct(s.at(-1)!, s.at(-2))}`;
  }).filter(Boolean);
  return out.length ? out.join("; ") : "Chưa đủ dữ liệu.";
}
function physicalLines(ph: { grades: string[]; dates: string[]; values: Record<string, Record<string, number>> }): string {
  if (!ph.dates.length) return "Chưa đủ dữ liệu.";
  const [cur, prev] = [ph.dates[0], ph.dates[1]];
  const out = ph.grades.map((g) => {
    const c = ph.values[g]?.[cur];
    if (c == null || isNoTrading(c)) return null;   // phiên No Trading không phải một mức giá
    return `${g}: ${vnum(c)} USD/T${pct(c, prev ? ph.values[g]?.[prev] : null)}`;
  }).filter(Boolean);
  return out.length ? `Phiên ${dm(cur)} — ${out.join("; ")}` : "Chưa đủ dữ liệu.";
}
function rawLines(p: { companies: string[]; dates: string[]; values: Record<string, Record<string, number>> }): string {
  if (!p.dates.length || !p.companies.length) return "Chưa đủ dữ liệu.";
  const avg = (day: string) => {
    const a = p.companies.map((c) => p.values[c]?.[day]).filter((v): v is number => v != null);
    return a.length ? a.reduce((s, x) => s + x, 0) / a.length : null;
  };
  const cur = p.dates[0];
  const vals = p.companies.map((c) => p.values[c]?.[cur]).filter((v): v is number => v != null);
  if (!vals.length) return "Chưa đủ dữ liệu.";
  const a = avg(cur)!;
  return `Mủ nước ngày ${dm(cur)}: ${vnum(Math.min(...vals))}–${vnum(Math.max(...vals))} đ/độ TSC, `
    + `TB ${vnum(a)}${pct(a, p.dates[1] ? avg(p.dates[1]) : null)}, ${vals.length} đơn vị.`;
}

function mqLines(c: MarketQuote, p: MarketQuote | null, date: string): string {
  let out = Object.keys(c.export_vrg?.prices ?? {}).map((g) => {
    const xk = c.export_vrg.prices?.[g];
    if (xk == null) return null;
    return `${g}: XK VRG ${vnum(xk)} USD/T${pct(xk, p?.export_vrg.prices?.[g])}`;
  }).filter(Boolean);
  if (!out.length) {
    out = Object.keys(c.domestic_private?.prices ?? {}).map((g) => {
      const v = c.domestic_private.prices?.[g];
      return v == null ? null : `${g}: NĐ tư nhân ${vnum(v / 1e6, 1)} tr.đ/T`;
    }).filter(Boolean);
  }
  return out.length ? `Phiếu ${dm(date)} — ${out.join("; ")}` : "Chưa đủ dữ liệu.";
}

/** Gom tóm tắt các nhóm (song song, chịu lỗi từng nhóm). */
export async function buildSummaries(): Promise<GroupMeta[]> {
  const [sheet, physical, purchase, inv, floorSch, mq] = await Promise.all([
    fetchSheet({ days: 30 }).catch(() => null),
    fetchPhysicalSheet().catch(() => null),
    fetchPurchaseSheet().catch(() => null),
    fetchInventory().catch(() => null),
    (async () => {
      const list = await listFloors().catch(() => []);
      return list.length ? await getFloor(list[0].lan) : null;
    })().catch(() => null),
    (async () => {
      const list = (await listQuotes().catch(() => [])).filter((s) => s.filled > 0);
      if (!list.length) return null;
      const [c, p] = await Promise.all([
        getQuote(list[0].as_of),
        list[1] ? getQuote(list[1].as_of) : Promise.resolve(null),
      ]);
      return { c, p, date: list[0].as_of };
    })().catch(() => null),
  ]);

  /* Giá sàn vs Thị trường: giá thị trường lấy phiên MỚI NHẤT CÓ SỐ (tự lùi về phiên trước khi
     hôm nay chưa có) — luôn ghi rõ ngày của phiên đã dùng để lãnh đạo biết đang so với ngày nào. */
  const floorData = (() => {
    const empty = { line: "Chưa đủ dữ liệu.", asOf: null as string | null, range: "—" };
    if (!floorSch || !sheet) return empty;
    const rows = compareFloorVsMarket(floorSch.items, sheet);
    if (!rows.length) return empty;
    const name = floorSch.title?.trim() || `lần ${floorSch.lan}`; // tên thật (vd "Lần thứ 16 năm 2026")
    const mktDates = [...new Set(rows.map((r) => r.marketAsOf))].sort();
    const mktLabel = mktDates.length > 1 ? `${dm(mktDates[0])}–${dm(mktDates.at(-1)!)}` : dm(mktDates[0]);
    const detail = rows.map((r) =>
      `${r.product}: sàn ${vnum(r.vrg)} vs TT ${vnum(r.market)} USD/T`
      + ` (${r.diffPct >= 0 ? "+" : ""}${r.diffPct.toFixed(1)}%; ${r.marketLabel} phiên ${dm(r.marketAsOf)})`,
    );
    return {
      line: `Giá sàn ${name} (áp dụng ${dmy(floorSch.as_of)}) so giá thị trường phiên ${mktLabel} — ${detail.join("; ")}`,
      asOf: floorSch.as_of,
      range: `${name} · áp dụng ${dmy(floorSch.as_of)} · TT phiên ${mktLabel}`,
    };
  })();

  const invLine = (() => {
    const c = inv?.[0];
    if (!c || c.ton_kho == null) return "Chưa đủ dữ liệu.";
    const tk = c.ton_kho;
    const prevTk = inv?.[1]?.ton_kho ?? null;
    const free = c.ton_kho_hd != null ? tk - c.ton_kho_hd : null;
    const dK = prevTk != null ? tk - prevTk : null;
    return `Tuần ${c.as_of}: tổng tồn kho ${vnum(tk)} tấn`
      + (dK != null ? ` (${dK >= 0 ? "+" : ""}${vnum(dK)} so tuần trước)` : "")
      + (c.ton_kho_hd != null ? `; đã có HĐ ${vnum(c.ton_kho_hd)}` : "")
      + (free != null ? `; tự do ${vnum(free)} tấn` : "") + ".";
  })();

  let rawLine = purchase ? rawLines(purchase) : "Chưa đủ dữ liệu.";
  const cup = Object.entries(mq?.c?.regions_cup ?? {}).filter(([, v]) => v != null) as [string, number][];
  if (cup.length) {
    const cv = cup.map((e) => e[1]);
    rawLine += ` Mủ chén: ${vnum(Math.min(...cv))}–${vnum(Math.max(...cv))} ${CUP_PRICE_UNIT_SHORT} (${cup.length} đơn vị).`;
  }

  // Ngày dữ liệu thực đã nạp cho từng nhóm (để hiển thị "nạp gì · khoảng ngày nào").
  const exDates = sheet ? sheet.rows.map((r) => r.as_of) : [];
  const fxDates = sheet
    ? sheet.rows.filter((r) => r.fx && Object.values(r.fx).some((v) => v != null)).map((r) => r.as_of)
    : [];
  const invDates = (inv ?? []).map((w) => w.as_of);

  const exSum = sheet ? exchangeLines(sheet) : "Chưa đủ dữ liệu.";
  const phSum = physical ? physicalLines(physical) : "Chưa đủ dữ liệu.";
  const mqSum = mq ? mqLines(mq.c, mq.p, mq.date) : "Chưa đủ dữ liệu.";
  const fxSum = sheet ? fxLines(sheet) : "Chưa đủ dữ liệu.";

  const mk = (
    key: string, label: string, summary: string, source: string,
    range: string, latest: string | null,
  ): GroupMeta => ({ key, label, summary, source, range, latest, ok: hasData(summary) });

  return [
    mk("exchanges", "Sàn giao dịch quốc tế (futures)", exSum,
      "Giá các sàn OSE · SHFE · SGX · MRB (quy đổi USD/tấn) — /api/prices/sheet",
      usedRange(exDates), latestOf(exDates)),
    mk("physical", "Giá physical (giao ngay)", phSum,
      "Giá giao ngay physical (Reuters, USD/tấn) — /api/prices/physical-sheet",
      usedRange(physical?.dates ?? []), latestOf(physical?.dates ?? [])),
    mk("marketquote", "Báo giá mủ thị trường (giá SVR)", mqSum,
      "Báo giá mủ SVR thị trường (phiếu nhập tay) — /api/market-quote",
      mq ? `phiếu ${dmy(mq.date)}${mq.p ? " (so phiếu trước)" : ""}` : "—", mq?.date ?? null),
    mk("fx", "Tỷ giá", fxSum,
      "Tỷ giá USD/VND · MYR · JPY · CNY (VCB · BNM · exchangerates)",
      usedRange(fxDates), latestOf(fxDates)),
    mk("inventory", "Tồn kho Tập đoàn", invLine,
      "Tồn kho Tập đoàn theo tuần — /api/inventory",
      usedRange(invDates, "tuần"), latestOf(invDates)),
    mk("floor", "Giá sàn Tập đoàn vs Thị trường", floorData.line,
      "Giá sàn công bố mới nhất vs giá thị trường phiên gần nhất — /api/floor + /api/prices/sheet",
      floorData.range, floorData.asOf),
    mk("raw", "Giá mủ nước & mủ chén nội địa", rawLine,
      "Giá mủ nước & mủ chén nội địa (đơn vị thành viên) — /api/prices/purchase-sheet",
      usedRange(purchase?.dates ?? []), latestOf(purchase?.dates ?? [])),
  ];
}
