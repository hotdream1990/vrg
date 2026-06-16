import { useEffect, useState } from "react";

import { type LatestRow, type ScanResult, fetchLatest, scanPrices } from "../../../lib/api-client";

/** Route "Quét Đa sàn" — đã implement thật:
    - Mở trang: nạp giá ĐÃ LƯU từ TimescaleDB (không cần quét lại mỗi lần).
    - Nút "Quét giá ngay": chạy crawler 6 sàn → ghi DB → làm mới bảng. */
export default function ScanPage() {
  const [latest, setLatest] = useState<LatestRow[]>([]);
  const [scanInfo, setScanInfo] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadLatest() {
    try {
      setLatest((await fetchLatest()).records);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được dữ liệu đã lưu");
    }
  }

  useEffect(() => {
    void loadLatest();
  }, []);

  async function scan() {
    setLoading(true);
    setError(null);
    try {
      setScanInfo(await scanPrices("all"));
      await loadLatest();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lỗi không xác định");
    } finally {
      setLoading(false);
    }
  }

  const updatedAt = latest
    .map((r) => r.ingested_at)
    .filter(Boolean)
    .sort()
    .at(-1);
  const dbOk = scanInfo?.db === "ok";

  // Nguồn kỳ vọng nhưng chưa có data (vd SGX/SICOM đang blocked) — tự ẩn khi đã có.
  const EXPECTED = ["anrpc", "fx", "sgx", "shfe", "tocom", "lgm"];
  const present = new Set(latest.map((r) => r.source));
  const missing = EXPECTED.filter((s) => !present.has(s));

  return (
    <>
      <div className="page-title" id="top">
        <div>
          <h2>◎ Quét Đa sàn</h2>
          <p>Quét giá cao su 6 sàn (ANRPC · FX · SHFE · TOCOM/OSE · SGX · LGM) và lưu vào TimescaleDB.</p>
        </div>
        <div className="actions">
          <button className="btn btn-primary" onClick={scan} disabled={loading}>
            {loading ? <><span className="spinner" /> Đang quét…</> : "⟳ Quét giá ngay"}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <div>
            <h3>Giá mới nhất đã lưu</h3>
            <div className="sub">
              {latest.length > 0
                ? `${latest.length} bản ghi · cập nhật ${updatedAt ? new Date(updatedAt).toLocaleString("vi-VN") : "—"}`
                : "Chưa có dữ liệu trong kho"}
            </div>
          </div>
          {scanInfo && (
            <span className={`db-badge ${dbOk ? "ok" : "warn"}`}>
              {dbOk ? `✓ Vừa ghi DB: ${scanInfo.persisted}` : `⚠ DB ${scanInfo.db}`}
              {scanInfo.run_id != null && ` · run #${scanInfo.run_id}`}
            </span>
          )}
        </div>

        {error && <div className="scan-err">Lỗi: {error} — kiểm tra API (cổng 8390) &amp; DB.</div>}

        {latest.length === 0 && !error ? (
          <div className="scan-empty">Kho trống — bấm “Quét giá ngay” để lấy &amp; lưu giá từ các sàn.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Sàn</th><th>Mặt hàng</th><th style={{ textAlign: "right" }}>Giá</th>
                <th>Đơn vị</th><th>Kỳ hạn</th><th>Loại giá</th><th>Ngày</th>
              </tr>
            </thead>
            <tbody>
              {latest.map((r, i) => (
                <tr key={i}>
                  <td>{r.source.toUpperCase()}</td>
                  <td style={{ fontWeight: 500 }}>{r.grade}</td>
                  <td style={{ textAlign: "right" }}>{r.price.toLocaleString()}</td>
                  <td>{r.unit}</td>
                  <td>{r.contract ? r.contract : "—"}</td>
                  <td>{r.price_type}</td>
                  <td>{r.as_of}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {scanInfo && (
          <div className="src-chips">
            {scanInfo.sources.map((s) => (
              <span key={s.source} className={`src-chip ${s.status === "ok" ? "ok" : "bad"}`} title={s.note ?? ""}>
                {s.status === "ok" ? "✓" : "⚠"} {s.source} ({s.count})
              </span>
            ))}
          </div>
        )}

        {missing.length > 0 && (
          <p style={{ color: "var(--muted)", fontSize: 12, margin: "12px 0 0" }}>
            ⚠ Chưa có data: <b style={{ color: "#fcd34d" }}>{missing.map((s) => s.toUpperCase()).join(", ")}</b>{" "}
            — SGX/SICOM là open item (cần licensed feed / capture từ browser; xem services/crawlers/README).
          </p>
        )}
      </div>
    </>
  );
}
