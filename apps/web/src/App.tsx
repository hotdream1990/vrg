import { useState, type CSSProperties } from "react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8390"; // backend FastAPI (cổng VRG)
const BRAND = { green: "#13A05A", navy: "#0E1B2C" };

type PriceRow = {
  source: string;
  grade: string;
  price: number;
  unit: string;
  price_type: string;
  as_of: string;
  contract?: string | null;
};
type SourceStatus = { source: string; status: string; count: number; note?: string | null };
type ScanResult = { records: PriceRow[]; sources: SourceStatus[] };

export default function App() {
  const [data, setData] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function scan() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/prices/scan`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData((await res.json()) as ScanResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lỗi không xác định");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ fontFamily: "Arial, sans-serif", color: BRAND.navy, background: "#fff", minHeight: "100vh", padding: 32, maxWidth: 980, margin: "0 auto" }}>
      <h1 style={{ color: BRAND.green, marginBottom: 4 }}>VRG · Quét giá cao su</h1>
      <p style={{ opacity: 0.7, marginTop: 0 }}>Bấm để quét đa sàn: ANRPC · FX · SHFE · TOCOM/OSE</p>

      <button
        onClick={scan}
        disabled={loading}
        style={{
          background: BRAND.green,
          color: "#fff",
          border: 0,
          borderRadius: 8,
          padding: "12px 24px",
          fontSize: 16,
          cursor: loading ? "wait" : "pointer",
        }}
      >
        {loading ? "Đang quét…" : "Quét giá ngay"}
      </button>

      {error && <p style={{ color: "#c0392b" }}>Lỗi: {error} — kiểm tra API đang chạy ở {API}</p>}

      {data && (
        <>
          <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 24, fontSize: 14 }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: `2px solid ${BRAND.navy}` }}>
                <th style={th}>Sàn</th>
                <th style={th}>Loại</th>
                <th style={{ ...th, textAlign: "right" }}>Giá</th>
                <th style={th}>Đơn vị</th>
                <th style={th}>Kỳ hạn</th>
                <th style={th}>Loại giá</th>
                <th style={th}>Ngày</th>
              </tr>
            </thead>
            <tbody>
              {data.records.map((r, i) => (
                <tr key={i} style={{ borderBottom: "1px solid #eee" }}>
                  <td style={td}>{r.source.toUpperCase()}</td>
                  <td style={{ ...td, fontWeight: 500 }}>{r.grade}</td>
                  <td style={{ ...td, textAlign: "right" }}>{r.price.toLocaleString()}</td>
                  <td style={td}>{r.unit}</td>
                  <td style={td}>{r.contract ?? "—"}</td>
                  <td style={td}>{r.price_type}</td>
                  <td style={td}>{r.as_of}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 16, display: "flex", gap: 8, flexWrap: "wrap" }}>
            {data.sources.map((s) => (
              <span
                key={s.source}
                title={s.note ?? ""}
                style={{
                  fontSize: 12,
                  padding: "4px 10px",
                  borderRadius: 6,
                  background: s.status === "ok" ? "#e1f5ee" : "#faeeda",
                  color: s.status === "ok" ? "#0f6e56" : "#854f0b",
                }}
              >
                {s.status === "ok" ? "✓" : "⚠"} {s.source} ({s.count})
              </span>
            ))}
          </div>
        </>
      )}
    </main>
  );
}

const th: CSSProperties = { padding: "8px 6px", fontWeight: 500 };
const td: CSSProperties = { padding: "7px 6px" };
