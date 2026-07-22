/* Báo cáo tổng hợp theo KỲ — trích xuất từ số liệu NGÀY ra biểu tuần/tháng/năm/khoảng tự chọn.
   Bám mẫu "Chỉ tiêu Biểu (1)-Tuần" (Tiêu thụ–Tồn kho) và "(2)-Tuần" (Thu mua):
   cộng dồn (sản lượng/doanh thu) · thời điểm (tồn kho, lấy ngày cuối kỳ) · bình quân gia quyền (giá).
   Mỗi đơn vị 1 dòng + dòng Tổng cộng; xuất Excel đúng mẫu. */

import { DownloadOutlined, FileDoneOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Segmented, Spin, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  type PeriodReport, type PeriodRow, downloadPeriodXlsx, fetchPeriodReport,
} from "../../../lib/unit-daily-client";
import { isoDate } from "../../../lib/date";
import { type Kind, fmtNum } from "../../../lib/unit-daily-fields";
import DateInput from "../sections/DateInput";
import "../../bulletin/bulletin.css";

type Col = { key: string; label: string; unit: string; note: string };

// Cột KHỚP file Excel xuất ra (app/services/unit_period_excel.py).
const PURCHASE_COLS: Col[] = [
  { key: "latex_wet", label: "SL thu mua mủ nước", unit: "tấn", note: "cộng dồn" },
  { key: "coagulum", label: "SL thu mua mủ chén", unit: "tấn", note: "cộng dồn" },
  { key: "total_purchase", label: "Tổng SL thu mua", unit: "tấn", note: "= nước + chén" },
  { key: "price_latex_avg", label: "Giá mủ nước BQ", unit: "đồng/độ TSC", note: "BQ gia quyền" },
  { key: "price_cup_avg", label: "Giá mủ chén BQ", unit: "đồng/độ TSC", note: "BQ gia quyền" },
  { key: "plan_tonnes", label: "Kế hoạch thu mua", unit: "tấn", note: "số liệu năm" },
  { key: "pct_plan", label: "% thực hiện KH", unit: "%", note: "= TH / KH" },
  { key: "consumption", label: "SL tiêu thụ mủ thu mua", unit: "tấn", note: "cộng dồn" },
  { key: "revenue_ty", label: "Doanh thu", unit: "tỷ đồng", note: "cộng dồn" },
  { key: "avg_sell_price", label: "Giá bán BQ", unit: "triệu đ/tấn", note: "= DT / SL" },
];

const CONSUMPTION_COLS: Col[] = [
  { key: "signed_lt_tonnes", label: "Đã ký HĐ dài hạn", unit: "tấn", note: "số liệu năm" },
  { key: "lt_export", label: "Dài hạn — XK/UTXK", unit: "tấn", note: "cộng dồn" },
  { key: "lt_domestic", label: "Dài hạn — Nội tiêu", unit: "tấn", note: "cộng dồn" },
  { key: "spot_export", label: "Chuyến — XK/UTXK", unit: "tấn", note: "cộng dồn" },
  { key: "spot_domestic", label: "Chuyến — Nội tiêu", unit: "tấn", note: "cộng dồn" },
  { key: "total_consumption", label: "Tổng tiêu thụ", unit: "tấn", note: "= 4 cột trên" },
  { key: "export_total", label: "Tổng XK/UTXK", unit: "tấn", note: "DH + chuyến" },
  { key: "domestic_total", label: "Tổng Nội tiêu", unit: "tấn", note: "DH + chuyến" },
  { key: "revenue_ty", label: "Doanh thu cao su", unit: "tỷ đồng", note: "cộng dồn" },
  { key: "avg_sell_price", label: "Giá bán BQ", unit: "triệu đ/tấn", note: "= DT / TT" },
  { key: "stock_finished", label: "Tồn kho thành phẩm", unit: "tấn", note: "thời điểm" },
  { key: "stock_finished_hd", label: "Trong đó đã có HĐ", unit: "tấn", note: "thời điểm" },
  { key: "stock_no_hd", label: "Chưa có HĐ", unit: "tấn", note: "= TK − đã HĐ" },
];
const TAIL_COLS: Col[] = [
  { key: "stock_material", label: "Tồn kho nguyên liệu", unit: "tấn", note: "thời điểm" },
  { key: "carry_lt_tonnes", label: "DH năm trước chuyển sang", unit: "tấn", note: "số liệu năm" },
  { key: "carry_spot_tonnes", label: "Chuyến năm trước chuyển sang", unit: "tấn", note: "số liệu năm" },
];
// Giá & % không cộng được ở dòng Tổng cộng.
const NO_SUM = new Set(["price_latex_avg", "price_cup_avg", "pct_plan", "avg_sell_price"]);

const KIND_OPTS = [
  { label: "Thu mua", value: "purchase" },
  { label: "Tiêu thụ – Tồn kho", value: "consumption" },
];
const PRESETS = ["Tuần này", "Tuần trước", "Tháng này", "Tháng trước", "Năm nay", "Tự chọn"] as const;
type Preset = (typeof PRESETS)[number];

/** Khoảng ngày của preset — tuần tính theo Thứ 2 → Chủ nhật (ISO). */
function rangeOf(p: Preset, today = new Date()): { from: string; to: string } | null {
  const d = new Date(today);
  if (p === "Tuần này" || p === "Tuần trước") {
    const dow = (d.getDay() + 6) % 7;                 // 0 = Thứ 2
    const mon = new Date(d); mon.setDate(d.getDate() - dow);
    if (p === "Tuần trước") mon.setDate(mon.getDate() - 7);
    const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
    return { from: isoDate(mon), to: isoDate(sun) };
  }
  if (p === "Tháng này" || p === "Tháng trước") {
    const m = d.getMonth() - (p === "Tháng trước" ? 1 : 0);
    return { from: isoDate(new Date(d.getFullYear(), m, 1)), to: isoDate(new Date(d.getFullYear(), m + 1, 0)) };
  }
  if (p === "Năm nay") {
    return { from: `${d.getFullYear()}-01-01`, to: `${d.getFullYear()}-12-31` };
  }
  return null;  // Tự chọn
}

export default function PeriodReportPage() {
  const [kind, setKind] = useState<Kind>("purchase");
  const [preset, setPreset] = useState<Preset>("Tuần này");
  const init = rangeOf("Tuần này")!;
  const [from, setFrom] = useState(init.from);
  const [to, setTo] = useState(init.to);
  const [data, setData] = useState<PeriodReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const pickPreset = (p: Preset) => {
    setPreset(p);
    const r = rangeOf(p);
    if (r) { setFrom(r.from); setTo(r.to); }
  };

  const load = useCallback(() => {
    if (from > to) { message.warning("Khoảng ngày không hợp lệ: từ ngày sau đến ngày."); return; }
    setLoading(true);
    fetchPeriodReport(kind, from, to)
      .then(setData).catch((e) => message.error(e.message)).finally(() => setLoading(false));
  }, [kind, from, to]);
  useEffect(() => { load(); }, [load]);

  const cols: Col[] = useMemo(() => {
    if (kind === "purchase") return PURCHASE_COLS;
    const grades = (data?.grades ?? []).map((g) => ({ key: `g:${g}`, label: g, unit: "tấn", note: "thời điểm" }));
    return [...CONSUMPTION_COLS, ...grades, ...TAIL_COLS];
  }, [kind, data]);

  const valueOf = (row: PeriodRow, key: string): number | null => {
    const v = key.startsWith("g:") ? row.stock_by_grade?.[key.slice(2)] : row[key];
    return typeof v === "number" ? v : null;
  };
  const totalOf = (key: string): number | null => {
    if (NO_SUM.has(key) || !data) return null;
    const vals = data.rows.map((r) => valueOf(r, key)).filter((v): v is number => v != null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) : null;
  };

  const exportXlsx = async () => {
    setSaving(true);
    try {
      await downloadPeriodXlsx(kind, from, to);
      message.success("Đã tải file Excel.");
    } catch (e) { message.error((e as Error).message); } finally { setSaving(false); }
  };

  const rows = data?.rows ?? [];
  const hasData = rows.some((r) => r.days > 0);

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><FileDoneOutlined style={{ marginRight: 8 }} />Báo cáo tổng hợp</h2>
          <p>
            Trích xuất từ số liệu nhập hàng ngày theo kỳ — <b>cộng dồn</b> sản lượng/doanh thu,
            tồn kho lấy <b>thời điểm cuối kỳ</b>, giá tính <b>bình quân gia quyền</b>.
          </p>
        </div>
      </div>

      <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <Segmented value={kind} onChange={(v) => setKind(v as Kind)} options={KIND_OPTS} />
        <Segmented value={preset} onChange={(v) => pickPreset(v as Preset)} options={[...PRESETS]} />
        <DateInput value={from} onChange={(v) => { setFrom(v); setPreset("Tự chọn"); }} style={{ width: 170 }} />
        <span style={{ color: "var(--muted)" }}>→</span>
        <DateInput value={to} onChange={(v) => { setTo(v); setPreset("Tự chọn"); }} style={{ width: 170 }} />
        <Button icon={<ReloadOutlined />} onClick={load}>Làm mới</Button>
        <Button type="primary" icon={<DownloadOutlined />} onClick={exportXlsx}
                loading={saving} disabled={!hasData}>Xuất Excel</Button>
      </div>

      <Spin spinning={loading}>
        <div className="card" style={{ padding: 0, overflow: "auto" }}>
          <table>
            <thead>
              <tr>
                <th style={{ minWidth: 120 }}>Khu vực</th>
                <th style={{ minWidth: 150 }}>Đơn vị</th>
                {cols.map((c) => (
                  <th key={c.key} className="r" style={{ minWidth: 118 }}>
                    {c.label}
                    <div style={{ fontWeight: 400, fontSize: 10.5, opacity: 0.6 }}>{c.unit}</div>
                    <div style={{ fontWeight: 400, fontSize: 10, opacity: 0.45, fontStyle: "italic" }}>{c.note}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.company} style={{ opacity: r.days ? 1 : 0.45 }}>
                  <td>{r.region ?? "—"}</td>
                  <td style={{ fontWeight: 500 }}>{r.company}</td>
                  {cols.map((c) => (
                    <td key={c.key} className="r">{fmtNum(valueOf(r, c.key), 2)}</td>
                  ))}
                </tr>
              ))}
              {!rows.length && !loading && (
                <tr><td colSpan={cols.length + 2} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                  Chưa có đơn vị nào.
                </td></tr>
              )}
              {rows.length > 0 && (
                <tr style={{ fontWeight: 600, background: "rgba(125,125,125,.08)" }}>
                  <td />
                  <td>Tổng cộng</td>
                  {cols.map((c) => (
                    <td key={c.key} className="r">{NO_SUM.has(c.key) ? "" : fmtNum(totalOf(c.key), 2)}</td>
                  ))}
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Spin>
      {!hasData && !loading && (
        <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 10 }}>
          Kỳ này chưa đơn vị nào nhập số liệu — chọn kỳ khác hoặc nhập ở các màn Báo cáo theo ngày.
        </p>
      )}
    </div>
  );
}
