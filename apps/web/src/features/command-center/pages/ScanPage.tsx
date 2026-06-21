import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  type LatestRow,
  type ScanResult,
  backfillPrices,
  fetchHistory,
  fetchLatest,
  scanPrices,
} from "../../../lib/api-client";
import ExchangeBoard from "../sections/ExchangeBoard";
import LiveCharts from "../sections/LiveCharts";
import LiveKpis from "../sections/LiveKpis";
import LiveScanTable from "../sections/LiveScanTable";
import PhysicalGradeTrend from "../sections/PhysicalGradeTrend";

type Point = { as_of: string; price: number };
const EXPECTED = ["anrpc", "fx", "sgx", "shfe", "tocom", "lgm"];

// % thay đổi phiên gần nhất so phiên trước (history sắp xếp tăng dần theo ngày).
const pct = (pts: Point[]): number | undefined =>
  pts.length >= 2 ? ((pts[pts.length - 1].price - pts[pts.length - 2].price) / pts[pts.length - 2].price) * 100 : undefined;

/** Route "Quét Đa sàn" — dashboard giá THẬT: KPI + nhiều chart (settlement sàn, vĩ mô FX,
    physical theo grade) backfill từ sàn + bảng chi tiết. Mở trang tự nạp từ DB. */
export default function ScanPage() {
  const [latest, setLatest] = useState<LatestRow[]>([]);
  const [shfe, setShfe] = useState<Point[]>([]);
  const [rss3, setRss3] = useState<Point[]>([]);
  const [tsr20, setTsr20] = useState<Point[]>([]);
  const [fxCny, setFxCny] = useState<Point[]>([]);
  const [scanInfo, setScanInfo] = useState<ScanResult | null>(null);
  const [boardKey, setBoardKey] = useState(0);
  const [loading, setLoading] = useState(false);
  const [backfilling, setBackfilling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fail = (e: unknown) => setError(e instanceof Error ? e.message : "Lỗi không xác định");

  const loadLatest = () => fetchLatest().then((r) => setLatest(r.records));
  const loadHistories = () =>
    Promise.all([
      fetchHistory("shfe", "RU", 90),
      fetchHistory("tocom", "RSS3", 60),
      fetchHistory("tocom", "TSR20", 60),
      fetchHistory("fx", "USD/CNY", 120),
    ]).then(([a, b, c, d]) => {
      setShfe(a.points);
      setRss3(b.points);
      setTsr20(c.points);
      setFxCny(d.points);
    });

  useEffect(() => {
    void loadLatest().catch(fail);
    void loadHistories().catch(fail);
  }, []);

  async function scan() {
    setLoading(true);
    setError(null);
    try {
      setScanInfo(await scanPrices("all"));
      await loadLatest();
      setBoardKey((k) => k + 1);
    } catch (e) {
      fail(e);
    } finally {
      setLoading(false);
    }
  }

  async function backfill() {
    setBackfilling(true);
    setError(null);
    try {
      await backfillPrices("shfe", 90);
      await backfillPrices("tocom", 30);
      await backfillPrices("fx", 120);
      await loadHistories();
      setBoardKey((k) => k + 1);
    } catch (e) {
      fail(e);
    } finally {
      setBackfilling(false);
    }
  }

  const deltas: Record<string, number> = {};
  const ds = pct(shfe);
  if (ds != null) deltas["shfe:RU"] = ds;
  const dr = pct(rss3);
  if (dr != null) deltas["tocom:RSS3"] = dr;

  // Physical theo grade (LGM, US cents/kg) cho chart cột — từ giá hiện tại.
  const lgm = latest.filter((r) => r.source === "lgm").sort((a, b) => b.price - a.price);
  const missing = EXPECTED.filter((s) => !new Set(latest.map((r) => r.source)).has(s));
  const updatedAt = latest.map((r) => r.ingested_at).filter(Boolean).sort().at(-1);
  const dbOk = scanInfo?.db === "ok";

  return (
    <>
      <div className="page-title" id="top">
        <div>
          <h2>◎ Dashboard Đa sàn (Live)</h2>
          <p>Giá thật 6 nguồn + lịch sử settlement/tỷ giá backfill từ sàn (SHFE · OSE · ECB) · ghi TimescaleDB.</p>
        </div>
        <div className="actions">
          <Link className="btn" to="/quan-ly-so-lieu/bang-gia-san">⊟ Quản lý số liệu</Link>
          <button className="btn" onClick={backfill} disabled={backfilling || loading}>
            {backfilling ? <><span className="spinner" /> Đang nạp…</> : "↻ Nạp lịch sử"}
          </button>
          <button className="btn btn-primary" onClick={scan} disabled={loading || backfilling}>
            {loading ? <><span className="spinner" /> Đang quét…</> : "⟳ Quét giá ngay"}
          </button>
        </div>
      </div>

      {error && <div className="scan-err" style={{ marginBottom: 12 }}>Lỗi: {error} — kiểm tra API (8390) &amp; DB.</div>}

      <LiveKpis latest={latest} deltas={deltas} />

      <ExchangeBoard reloadKey={boardKey} />

      <LiveCharts
        shfe={shfe}
        rss3={rss3}
        tsr20={tsr20}
        fxCny={fxCny}
        physLabels={lgm.map((r) => r.grade)}
        physValues={lgm.map((r) => r.price)}
      />

      <PhysicalGradeTrend rows={latest.filter((r) => r.price_type === "physical")} />

      <div className="card" style={{ marginBottom: 18 }}>
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
        {latest.length === 0 && !error ? (
          <div className="scan-empty">Kho trống — bấm “Quét giá ngay”.</div>
        ) : (
          <LiveScanTable latest={latest} scanInfo={scanInfo} missing={missing} />
        )}
      </div>
    </>
  );
}
