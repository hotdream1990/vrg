import { ArrowDownOutlined, ArrowUpOutlined, MinusOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";

import { type FloorModel, type ScenarioResult, fetchScenarios } from "../../../../lib/floor-suggest-client";

const fmt = (n: number | null) => (n == null ? "—" : n.toLocaleString("vi-VN"));
const delta = (v: number | null, base: number | null) =>
  v == null || base == null ? "" : (v - base > 0 ? "+" : "") + (v - base).toLocaleString("vi-VN");

/** Ma trận kịch bản giá sàn Giảm / Cơ sở / Tăng theo cú sốc rổ chỉ số (Bull/Base/Bear). */
export default function ScenarioMatrix({ asOf, model }: { asOf: string; model: FloorModel }) {
  const [data, setData] = useState<ScenarioResult | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setErr("");
    fetchScenarios(asOf, model).then(setData).catch((e) => setErr(e.message));
  }, [asOf, model]);

  const s = data?.shock_pct;
  return (
    <div className="card" style={{ padding: 0, overflow: "auto" }}>
      <div style={{ padding: "12px 16px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <h3 style={{ margin: 0 }}>Ma trận kịch bản giá sàn (Giảm / Cơ sở / Tăng)</h3>
        {s != null && (
          <span className="chip" style={{ fontSize: 12 }}>
            Giả định rổ chỉ số ±{String(s).replace(".", ",")}% (≈ 1 độ lệch chuẩn biến động giữa các lần)
          </span>
        )}
      </div>
      {err && <div className="blt-error" style={{ margin: "0 16px 12px" }}>{err}</div>}
      {data?.error && <div className="blt-error" style={{ margin: "0 16px 12px" }}>{data.error}</div>}
      <table style={{ fontSize: 13 }}>
        <thead><tr>
          <th>Chủng loại</th>
          <th className="r">Lần trước</th>
          <th className="r" style={{ color: "#e11d48" }}><ArrowDownOutlined /> GIẢM (−{s != null ? String(s).replace(".", ",") : "?"}%)</th>
          <th className="r"><MinusOutlined /> CƠ SỞ</th>
          <th className="r" style={{ color: "#16a34a" }}><ArrowUpOutlined /> TĂNG (+{s != null ? String(s).replace(".", ",") : "?"}%)</th>
        </tr></thead>
        <tbody>
          {(data?.items ?? []).map((it) => (
            <tr key={it.grade}>
              <td style={{ fontWeight: 500 }}>
                {it.grade}
                {it.unit && it.unit !== "USD/T" && (
                  <span style={{ fontSize: 11, marginLeft: 6, color: "var(--muted)", fontWeight: 400 }}>({it.unit})</span>
                )}
              </td>
              <td className="r" style={{ color: "var(--muted)" }}>{fmt(it.prev)}</td>
              <td className="r" style={{ color: "#e11d48" }}>
                {fmt(it.bear)}<span style={{ fontSize: 11, marginLeft: 4, opacity: 0.8 }}>{delta(it.bear, it.base)}</span>
              </td>
              <td className="r" style={{ fontWeight: 700 }}>{fmt(it.base)}</td>
              <td className="r" style={{ color: "#16a34a" }}>
                {fmt(it.bull)}<span style={{ fontSize: 11, marginLeft: 4, opacity: 0.8 }}>{delta(it.bull, it.base)}</span>
              </td>
            </tr>
          ))}
          {!data?.items?.length && !err && !data?.error && (
            <tr><td colSpan={5} style={{ textAlign: "center", padding: 18, color: "var(--muted)" }}>Đang tải…</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
