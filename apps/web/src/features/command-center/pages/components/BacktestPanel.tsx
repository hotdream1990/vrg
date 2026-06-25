import { useEffect, useState } from "react";

import {
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
export default function BacktestPanel({ grade }: { grade: string }) {
  const [model, setModel] = useState<FloorModel>("v1");
  const [v1, setV1] = useState<BacktestResult | null>(null);
  const [v2, setV2] = useState<BacktestResult | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setErr("");
    Promise.all([fetchFloorBacktest(grade, "v1"), fetchFloorBacktest(grade, "v2")])
      .then(([a, b]) => { setV1(a); setV2(b); })
      .catch((e) => setErr(e.message));
  }, [grade]);

  const cur = model === "v1" ? v1 : v2;
  const m = cur?.metrics;

  return (
    <div className="card">
      <div className="card-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
        <h3>Kiểm định mô hình (Backtest) — {grade}</h3>
        <div style={{ display: "flex", gap: 6 }}>
          {(["v1", "v2"] as FloorModel[]).map((mo) => (
            <button
              key={mo}
              onClick={() => setModel(mo)}
              className="blt-date-input"
              style={{ cursor: "pointer", fontWeight: model === mo ? 700 : 400,
                background: model === mo ? "var(--accent, #16a34a)" : undefined,
                color: model === mo ? "#fff" : undefined }}
            >
              {mo === "v1" ? "Rổ 4 futures (khuyến nghị)" : "Đa biến + mủ nước (đối chiếu)"}
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
            />
          : <div className="scan-empty">Chưa đủ dữ liệu để backtest grade này.</div>}
      </div>

      {v1 && v2 && (
        <div style={{ fontSize: 12, color: "var(--muted)", margin: "8px 0" }}>
          So sánh: <b>Rổ 4 futures</b> MAPE {v1.metrics.mape ?? "—"}% · đúng hướng {v1.metrics.hit ?? "—"}%
          {"  •  "}<b>Đa biến</b> MAPE {v2.metrics.mape ?? "—"}% · đúng hướng {v2.metrics.hit ?? "—"}%
        </div>
      )}

      <div style={{ overflow: "auto", maxHeight: 280 }}>
        <table style={{ fontSize: 13 }}>
          <thead><tr>
            <th>Lần</th><th>Ngày</th><th className="r">Thực (FOB)</th>
            <th className="r">Dự báo</th><th className="r">Lệch</th><th className="r">Lệch %</th>
          </tr></thead>
          <tbody>
            {(cur?.points ?? []).slice().reverse().map((p) => {
              const big = Math.abs(p.err_pct) > 6;
              return (
                <tr key={p.as_of}>
                  <td>{p.lan}</td><td>{p.as_of}</td>
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
