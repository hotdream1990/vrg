import { useEffect, useState } from "react";

import {
  type LatestRow,
  type ScanResult,
  backfillPrices,
  fetchHistory,
  fetchLatest,
  scanPrices,
} from "../../../lib/api-client";
import HistoryLineChart from "../charts/HistoryLineChart";
import LiveKpis from "../sections/LiveKpis";
import LiveScanTable from "../sections/LiveScanTable";

type Point = { as_of: string; price: number };
const EXPECTED = ["anrpc", "fx", "sgx", "shfe", "tocom", "lgm"];

// % thay đổi phiên gần nhất so phiên trước (history sắp xếp tăng dần theo ngày).
const pct = (pts: Point[]): number | undefined =>
  pts.length >= 2 ? ((pts[pts.length - 1].price - pts[pts.length - 2].price) / pts[pts.length - 2].price) * 100 : undefined;

/** Route "Quét Đa sàn" — dashboard giá THẬT: KPI + chart lịch sử (backfill từ sàn) + bảng chi tiết.
    Mở trang tự nạp từ DB (không cần click); "Quét giá ngay" = cập nhật, "Nạp lịch sử" = backfill. */
export default function ScanPage() {
  const [latest, setLatest] = useState<LatestRow[]>([]);
  const [shfeHist, setShfeHist] = useState<Point[]>([]);
  const [tocomHist, setTocomHist] = useState<Point[]>([]);
  const [scanInfo, setScanInfo] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [backfilling, setBackfilling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fail = (e: unknown) => setError(e instanceof Error ? e.message : "Lỗi không xác định");

  const loadLatest = () => fetchLatest().then((r) => setLatest(r.records));
  const loadHistories = () =>
    Promise.all([fetchHistory("shfe", "RU", 90), fetchHistory("tocom", "RSS3", 60)]).then(([a, b]) => {
      setShfeHist(a.points);
      setTocomHist(b.points);
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
      await loadHistories();
    } catch (e) {
      fail(e);
    } finally {
      setBackfilling(false);
    }
  }

  const deltas: Record<string, number> = {};
  const ds = pct(shfeHist);
  if (ds != null) deltas["shfe:RU"] = ds;
  const dt = pct(tocomHist);
  if (dt != null) deltas["tocom:RSS3"] = dt;

  const missing = EXPECTED.filter((s) => !new Set(latest.map((r) => r.source)).has(s));
  const updatedAt = latest.map((r) => r.ingested_at).filter(Boolean).sort().at(-1);
  const dbOk = scanInfo?.db === "ok";

  return (
    <>
      <div className="page-title" id="top">
        <div>
          <h2>◎ Dashboard Đa sàn (Live)</h2>
          <p>Giá thật 6 nguồn + lịch sử settlement backfill từ sàn (SHFE · OSE) · ghi TimescaleDB.</p>
        </div>
        <div className="actions">
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

      <div className="grid-2">
        <Chart title="SHFE · Cao su thiên nhiên" sub={`Settlement kỳ hạn max-volume · CNY/tấn · ${shfeHist.length} phiên`} points={shfeHist} label="SHFE RU (CNY/tấn)" color="#38bdf8" />
        <Chart title="OSE/TOCOM · RSS3" sub={`Settlement max trading value · JPY/kg · ${tocomHist.length} phiên`} points={tocomHist} label="OSE RSS3 (JPY/kg)" color="#22c55e" />
      </div>

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

function Chart({ title, sub, points, label, color }: { title: string; sub: string; points: Point[]; label: string; color: string }) {
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3>{title}</h3>
          <div className="sub">{sub}</div>
        </div>
        <span className="chip">Dữ liệu thật</span>
      </div>
      <div className="chart-wrap">
        {points.length > 0 ? (
          <HistoryLineChart points={points} label={label} color={color} />
        ) : (
          <div className="scan-empty">Chưa có lịch sử — bấm “Nạp lịch sử”.</div>
        )}
      </div>
    </div>
  );
}
