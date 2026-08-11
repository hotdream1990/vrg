import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  downloadPublished,
  getPublishedDetail,
  type BulletinDraft,
} from "../../../lib/bulletin-client";
import { fmtPrice } from "../../../lib/no-trading";
import "../../bulletin/bulletin.css";

/* ── Icons ── */
const IconDownload = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
  </svg>
);

/* ── Helpers ── */
const fmt = fmtPrice;  // giá 0 = No Trading (quy ước chung, xem lib/no-trading)
const fmtPct = (v: number | null) => (v != null ? `${v > 0 ? "+" : ""}${v.toFixed(1)}%` : "");
const fmtChg = (v: number | null) => (v != null ? `${v > 0 ? "+" : ""}${v}` : "");
const cls = (v: number | null) => (v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "flat");

export default function BulletinDetailPage() {
  const { filename = "" } = useParams();
  const name = decodeURIComponent(filename);
  const [d, setD] = useState<BulletinDraft | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    getPublishedDetail(name)
      .then((r) => { if (alive) setD(r); })
      .catch((e) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [name]);

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <Link to="/ban-tin" className="blt-back">← Danh sách bản tin</Link>
          <h2>Bản tin ngày {d?.report_date ?? ""}</h2>
          <p>{name}</p>
        </div>
        <div className="actions">
          <button className="btn btn-primary" onClick={() => downloadPublished(name).catch((e) => setError(e.message))}>
            <IconDownload /> Tải
          </button>
        </div>
      </div>

      {error && <div className="blt-error">{error}</div>}
      {!d && !error && (
        <div className="blt-loading"><span className="spinner" /> Đang tải chi tiết...</div>
      )}

      {d && (
        <div className="blt-sections">
          {/* I. Giá CSTN thế giới */}
          <div className="card blt-section">
            <div className="blt-section-header"><h3>I. Giá cao su thiên nhiên thế giới</h3></div>
            <table className="blt-list-table">
              <thead><tr>
                <th>Sàn</th><th>Mặt hàng</th><th>Đơn vị</th>
                <th className="r">Giá ({d.prev_date})</th><th className="r">Giá ({d.report_date})</th>
                <th className="r">+/-</th><th className="r">%</th>
              </tr></thead>
              <tbody>
                {d.world_prices.map((w, i) => (
                  <tr key={i}>
                    <td>{w.exchange}</td><td>{w.grade}</td><td>{w.unit}</td>
                    <td className="r">{fmt(w.price_prev)}</td><td className="r">{fmt(w.price_curr)}</td>
                    <td className={`r ${cls(w.change_abs)}`}>{fmtChg(w.change_abs)}</td>
                    <td className={`r ${cls(w.change_abs)}`}>{fmtPct(w.change_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* II. Giá vật chất (Reuters) */}
          <div className="card blt-section">
            <div className="blt-section-header"><h3>II. Giá vật chất (Reuters)</h3></div>
            {d.physical_prices.length > 0 ? (
              <table className="blt-list-table">
                <thead><tr>
                  <th>Mặt hàng</th>
                  <th className="r">Giá ({d.physical_prev_label || d.prev_date})</th>
                  <th className="r">Giá ({d.physical_curr_label || d.report_date})</th>
                  <th className="r">+/-</th><th className="r">%</th>
                </tr></thead>
                <tbody>
                  {d.physical_prices.map((p, i) => (
                    <tr key={i}>
                      <td>{p.grade}</td>
                      <td className="r">{fmt(p.price_prev)}</td><td className="r">{fmt(p.price_curr)}</td>
                      <td className={`r ${cls(p.change_abs)}`}>{fmtChg(p.change_abs)}</td>
                      <td className={`r ${cls(p.change_abs)}`}>{fmtPct(p.change_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p style={{ color: "var(--muted)", fontSize: 13 }}>
                Không có giá vật chất giao dịch cho ngày {d.report_date}.
              </p>
            )}
          </div>

          {/* III. Giá sàn VRG */}
          <div className="card blt-section">
            <div className="blt-section-header"><h3>III. Giá sàn VRG — {d.vrg_floor_curr_label}</h3></div>
            <table className="blt-list-table">
              <thead><tr><th>Loại</th><th className="r">FOB (USD/T)</th><th className="r">Trong nước (VND)</th></tr></thead>
              <tbody>
                {d.vrg_floor_curr
                  .map((v, i) => ({ v, p: d.vrg_floor_prev[i] }))
                  // Ẩn dòng không có giá ở cả 2 lần (vd SkimBlock chưa nhập).
                  .filter(({ v, p }) =>
                    v.fob_usd != null || v.domestic_vnd != null ||
                    p?.fob_usd != null || p?.domestic_vnd != null)
                  .map(({ v }) => (
                    <tr key={v.grade}>
                      <td>{v.grade}</td><td className="r">{fmt(v.fob_usd)}</td><td className="r">{fmt(v.domestic_vnd)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            {d.raw_materials.length > 0 && (
              <p style={{ marginTop: 14, color: "var(--muted)", fontSize: 13 }}>
                <strong>Mủ nguyên liệu:</strong>{" "}
                {d.raw_materials.map((r) => `Khu vực ${r.region}: ${r.price_text}`).join(" · ")}
              </p>
            )}
          </div>

          {/* IV. Phân tích thị trường */}
          <div className="card blt-section">
            <div className="blt-section-header"><h3>IV. Thông tin thị trường</h3></div>
            {d.exchange_summary.map((s, i) => (
              <p key={`e${i}`} style={{ fontSize: 13, lineHeight: 1.6, margin: "0 0 8px" }}>{s}</p>
            ))}
            {d.physical_summary && (
              <p style={{ fontSize: 13, lineHeight: 1.6, margin: "0 0 8px" }}>{d.physical_summary}</p>
            )}
            {d.market_analysis.map((s, i) => (
              <p key={`a${i}`} style={{ fontSize: 13, lineHeight: 1.6, margin: "0 0 8px", color: "var(--muted)" }}>{s}</p>
            ))}
            {d.source_urls.length > 0 && (
              <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 10 }}>
                Nguồn: {d.source_urls.join(" · ")}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
