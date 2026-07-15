import { useEffect, useState } from "react";

import {
  type BacktestMetrics,
  type BacktestResult,
  type FloorModel,
  fetchFloorBacktest,
} from "../../../../lib/floor-suggest-client";
import BacktestChart from "../../charts/BacktestChart";

const fmt = (n: number | null) => (n == null ? "—" : n.toLocaleString("vi-VN"));
/** Màu theo mục tiêu đề án: MAPE ≤6% đạt (xanh), ≤10% chấp nhận (vàng), >10% (đỏ). */
const mapeColor = (m?: number | null) =>
  m == null ? "var(--muted)" : m <= 6 ? "#16a34a" : m <= 10 ? "#ca8a04" : "#e11d48";

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ flex: "1 1 120px", padding: "10px 14px", background: "var(--card-2, #f6faf7)", borderRadius: 8 }}>
      <div style={{ fontSize: 12, color: "var(--muted)" }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color ?? "var(--text)" }}>{value}</div>
    </div>
  );
}

/** Kiểm định mô hình: backtest toàn chuỗi 1 grade, đo độ khớp dự báo vs giá sàn thực + so v1/v2. */
export default function BacktestPanel({ grade, model, onModel }: {
  grade: string; model: FloorModel; onModel: (m: FloorModel) => void;
}) {
  const [v1, setV1] = useState<BacktestResult | null>(null);
  const [v1i, setV1i] = useState<BacktestResult | null>(null);
  const [v1f, setV1f] = useState<BacktestResult | null>(null);
  const [v2, setV2] = useState<BacktestResult | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setErr("");
    Promise.all([fetchFloorBacktest(grade, "v1"), fetchFloorBacktest(grade, "v1i"),
      fetchFloorBacktest(grade, "v1f"), fetchFloorBacktest(grade, "v2")])
      .then(([a, c, f, b]) => { setV1(a); setV1i(c); setV1f(f); setV2(b); })
      .catch((e) => setErr(e.message));
  }, [grade]);

  const cur = model === "v1" ? v1 : model === "v1i" ? v1i : model === "v1f" ? v1f : v2;
  const m = cur?.metrics;

  return (
    <div className="card">
      <div className="card-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
        <h3>Kiểm định mô hình (Backtest) — {grade}</h3>
        <div style={{ display: "flex", gap: 6 }}>
          {(["v1", "v1i", "v1f", "v2"] as FloorModel[]).map((mo) => (
            <button
              key={mo}
              onClick={() => onModel(mo)}
              className="blt-date-input"
              style={{ cursor: "pointer", fontWeight: model === mo ? 700 : 400,
                background: model === mo ? "var(--accent, #16a34a)" : undefined,
                color: model === mo ? "#fff" : undefined }}
            >
              {mo === "v1" ? "Rổ futures" : mo === "v1i" ? "+ Tồn kho tổng"
                : mo === "v1f" ? "+ Tồn kho tự do" : "Đa biến + mủ nước"}
            </button>
          ))}
        </div>
      </div>

      {err && <div className="blt-error">{err}</div>}
      <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 0 }}>
        Mỗi lần ban hành được dự báo CHỈ từ dữ liệu TRƯỚC đó (walk-forward, không rò rỉ tương lai),
        rồi so với giá sàn thực tế. Mục tiêu đề án: MAPE ≤ 6%.
      </p>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
        <Stat label="MAPE (sai số %)" value={m?.mape != null ? `${m.mape}%` : "—"} color={mapeColor(m?.mape)} />
        <Stat label="MAE (USD/T)" value={fmt(m?.mae ?? null)} />
        <Stat label="RMSE (USD/T)" value={fmt(m?.rmse ?? null)} />
        <Stat label="Đúng hướng" value={m?.hit != null ? `${m.hit}%` : "—"} color={m?.hit != null && m.hit >= 70 ? "#16a34a" : undefined} />
        <Stat label="Số lần kiểm" value={fmt(m?.n ?? null)} />
      </div>

      <div style={{ height: 300 }}>
        {cur && cur.points.length > 0
          ? <BacktestChart
              labels={cur.points.map((p) => p.as_of)}
              actual={cur.points.map((p) => p.actual)}
              pred={cur.points.map((p) => p.pred)}
              free={cur.points.map((p) => p.ton_free ?? null)}
            />
          : <div className="scan-empty">Chưa đủ dữ liệu để backtest grade này.</div>}
      </div>

      {v1 && v1i && v1f && (() => {
        const base = v1.metrics;
        const verdict = (mt: BacktestMetrics): [string, string] => {
          const mapeOk = (mt.mape ?? 0) <= (base.mape ?? 0);
          const hitOk = (mt.hit ?? 0) >= (base.hit ?? 0);
          return mapeOk && hitOk ? ["TỐT HƠN", "#16a34a"]
            : !mapeOk && !hitOk ? ["TỆ HƠN", "#e11d48"] : ["LẪN LỘN", "#ca8a04"];
        };
        const Row = ({ label, mt, v }: { label: string; mt: BacktestMetrics; v?: [string, string] }) => (
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "baseline" }}>
            <span style={{ minWidth: 168, fontWeight: 500 }}>{label}</span>
            <span>MAPE <b style={{ color: v?.[1] }}>{mt.mape}%</b></span>
            <span>điều chỉnh <b>{mt.mape_move ?? "—"}%</b></span>
            <span>đúng hướng <b>{mt.hit}%</b></span>
            {v && <span style={{ color: v[1], fontWeight: 700 }}>{v[0]}</span>}
          </div>
        );
        return (
          <div style={{ margin: "8px 0", padding: "10px 14px", background: "var(--card-2, #f6faf7)", borderRadius: 8, fontSize: 13, display: "grid", gap: 5 }}>
            <b>Tác động Tồn kho lên mô hình ({grade})</b>
            <Row label="Trước · Rổ futures" mt={base} />
            <Row label="+ Tồn kho TỔNG" mt={v1i.metrics} v={verdict(v1i.metrics)} />
            <Row label="+ Tồn kho TỰ DO (chưa có HĐ)" mt={v1f.metrics} v={verdict(v1f.metrics)} />
            {v2 && <div style={{ fontSize: 12, color: "var(--muted)" }}>(Tham chiếu — Đa biến + mủ nước: MAPE {v2.metrics.mape ?? "—"}% · đúng hướng {v2.metrics.hit ?? "—"}%)</div>}
          </div>
        );
      })()}

      <div style={{ overflow: "auto", maxHeight: 280 }}>
        <table style={{ fontSize: 13 }}>
          <thead><tr>
            <th>Ngày phát hành</th><th className="r">Thực (FOB)</th>
            <th className="r">Dự báo</th><th className="r">Lệch</th><th className="r">Lệch %</th>
          </tr></thead>
          <tbody>
            {(cur?.points ?? []).slice().reverse().map((p) => {
              const big = Math.abs(p.err_pct) > 6;
              return (
                <tr key={p.as_of}>
                  <td>{p.as_of}</td>
                  <td className="r">{fmt(p.actual)}</td>
                  <td className="r" style={{ color: "var(--muted)" }}>{fmt(p.pred)}</td>
                  <td className="r" style={{ color: big ? "#e11d48" : "#16a34a", fontWeight: 600 }}>
                    {p.err > 0 ? "+" : ""}{fmt(p.err)}
                  </td>
                  <td className="r" style={{ color: big ? "#e11d48" : "var(--muted)" }}>
                    {p.err_pct > 0 ? "+" : ""}{p.err_pct}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
