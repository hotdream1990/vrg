import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import type { BulletinDraft } from "../../../lib/bulletin-client";
import {
  createDraft,
  generateMarketAnalysis,
  generatePdf,
  updateDraft,
} from "../../../lib/bulletin-client";

import { useAuth } from "../../auth/AuthContext";
import BulletinImageSettings from "../../bulletin/BulletinImageSettings";
import DateInput from "../sections/DateInput";
import "../../bulletin/bulletin.css";

/* ── SVG Icons ── */

const IconClipboard = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
  </svg>
);
const IconSave = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" /><polyline points="17 21 17 13 7 13 7 21" /><polyline points="7 3 7 8 15 8" />
  </svg>
);
const IconDownload = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
  </svg>
);
const IconZap = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
);
const IconAlertCircle = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
  </svg>
);
const IconAlertTriangle = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);
const IconCheck = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);
const IconEdit = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
  </svg>
);
const IconDatabase = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" /><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" />
  </svg>
);

/* ── Helpers ── */

const fmt = (v: number | null) => (v != null ? v.toLocaleString() : "—");
const fmtPct = (v: number | null) => (v != null ? `${v > 0 ? "+" : ""}${v.toFixed(1)}%` : "");
const fmtChg = (v: number | null) => (v != null ? `${v > 0 ? "+" : ""}${v}` : "");
const cls = (v: number | null) => (v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "flat");

export default function BulletinPage() {
  const { canEdit } = useAuth();
  const [draft, setDraft] = useState<BulletinDraft | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [searchParams] = useSearchParams();
  const [dateInput, setDateInput] = useState(() => {
    const q = searchParams.get("date"); // mở lại nháp từ danh sách: ?date=YYYY-MM-DD
    if (q && /^\d{4}-\d{2}-\d{2}$/.test(q)) return q;
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0, 10); // YYYY-MM-DD for <input type=date>
  });

  const dateStr = useCallback(() => {
    const [y, m, d] = dateInput.split("-");
    return `${d}-${m}-${y}`;
  }, [dateInput]);

  /* ── Actions ── */

  const handleCreate = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await createDraft(dateStr());
      setDraft(d);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [dateStr]);

  // Mở từ danh sách nháp (?date=…) → tự tạo/nạp draft (áp overrides đã lưu) một lần.
  const openedRef = useRef(false);
  useEffect(() => {
    if (openedRef.current || !searchParams.get("date")) return;
    openedRef.current = true;
    handleCreate();
  }, [searchParams, handleCreate]);

  const handleSave = async () => {
    if (!draft) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateDraft(
        {
          exchange_summary: draft.exchange_summary,
          physical_summary: draft.physical_summary,
          market_analysis: draft.market_analysis,
          source_urls: draft.source_urls,
        },
        dateStr()
      );
      setDraft(updated);
      setNotice("Đã lưu bản tin.");
      setTimeout(() => setNotice(null), 2500);
    } catch (e: any) {
      setError(`Lưu thất bại: ${e?.message || e}`);
    } finally {
      setSaving(false);
    }
  };

  const handleExportPdf = async () => {
    if (!draft) return;
    setExportingPdf(true);
    setError(null);
    try {
      // Tự lưu nội dung đang có (gồm phân tích AI) trước khi xuất → PDF không thiếu mục IV.3.
      await updateDraft(
        {
          exchange_summary: draft.exchange_summary,
          physical_summary: draft.physical_summary,
          market_analysis: draft.market_analysis,
          source_urls: draft.source_urls,
        },
        dateStr()
      );
      await generatePdf(dateStr());
    } catch (e: any) {
      setError(`Xuất PDF thất bại: ${e.message}`);
    } finally {
      setExportingPdf(false);
    }
  };

  /* ── Inline edit helpers ── */

  const updateField = <K extends keyof BulletinDraft>(key: K, val: BulletinDraft[K]) =>
    setDraft((prev) => (prev ? { ...prev, [key]: val } : prev));

  const updateAnalysis = (idx: number, val: string) => {
    if (!draft) return;
    const items = [...draft.market_analysis];
    items[idx] = val;
    updateField("market_analysis", items);
  };

  const updateExchange = (idx: number, val: string) => {
    if (!draft) return;
    const items = [...draft.exchange_summary];
    items[idx] = val;
    updateField("exchange_summary", items);
  };

  const addAnalysis = () => {
    if (!draft) return;
    updateField("market_analysis", [...draft.market_analysis, ""]);
  };

  const removeAnalysis = (idx: number) => {
    if (!draft) return;
    updateField("market_analysis", draft.market_analysis.filter((_, i) => i !== idx));
  };

  const aiAnalyze = async () => {
    if (!draft) return;
    setAiBusy(true);
    setError(null);
    try {
      const r = await generateMarketAnalysis();
      setDraft((prev) => prev ? {
        ...prev,
        market_analysis: r.paragraphs,
        source_urls: Array.from(new Set([...prev.source_urls.filter(Boolean), ...r.source_urls])),
      } : prev);
    } catch (e) {
      setError(`Phân tích AI thất bại: ${(e as Error).message}`);
    } finally {
      setAiBusy(false);
    }
  };

  /* ── Render ── */

  // Viewer (chỉ xem) không được vào trình soạn bản tin.
  if (!canEdit) {
    return (
      <div className="main">
        <div className="page-title"><div><h2>Soạn bản tin ngày</h2></div></div>
        <div className="card" style={{ padding: 24, textAlign: "center", color: "var(--muted)" }}>
          Tài khoản của bạn chỉ có quyền xem. Bạn có thể xem các{" "}
          <Link className="blt-link" to="/ban-tin">bản tin đã xuất bản</Link>, nhưng không soạn/xuất bản tin mới.
        </div>
      </div>
    );
  }

  return (
    <div className="main">
      {/* Header */}
      <div className="page-title">
        <div>
          <Link to="/ban-tin" className="blt-back">← Danh sách bản tin</Link>
          <h2><IconClipboard /> Bản tin Thị trường Cao su Ngày</h2>
          <p>Tạo, xem trước và chỉnh sửa bản tin trước khi xuất PDF</p>
        </div>
        <div className="actions">
          {draft && (
            <>
              <button className="btn" onClick={handleSave} disabled={saving}>
                {saving ? <span className="spinner" /> : <IconSave />} Lưu
              </button>
              <button className="btn btn-primary" onClick={handleExportPdf} disabled={exportingPdf}>
                {exportingPdf ? <span className="spinner" /> : <IconDownload />} Xuất PDF
              </button>
            </>
          )}
        </div>
      </div>

      {/* Date picker + Create */}
      <div className="blt-toolbar">
        <label className="blt-date-label">
          Ngày bản tin:{" "}
          <DateInput value={dateInput} onChange={setDateInput} />
        </label>
        <button className="btn btn-primary" onClick={() => handleCreate()} disabled={loading}>
          {loading ? <span className="spinner" /> : <IconZap />} Tạo bản tin
        </button>
      </div>

      {/* Image settings panel */}
      <BulletinImageSettings
        open={showSettings}
        onToggle={() => setShowSettings((v) => !v)}
      />

      {error && <div className="blt-error"><IconAlertCircle /> {error}</div>}
      {notice && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#16a34a",
          background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8,
          padding: "8px 12px", fontSize: 13, marginTop: 8 }}>
          <IconCheck /> {notice}
        </div>
      )}

      {!draft && !loading && (
        <div className="blt-empty">
          <div className="blt-empty-icon"><IconClipboard /></div>
          <h3>Chưa có bản tin</h3>
          <p>Chọn ngày và nhấn "Tạo bản tin" để bắt đầu</p>
        </div>
      )}

      {loading && (
        <div className="blt-loading">
          <span className="spinner" /> Đang quét giá từ các sàn...
        </div>
      )}

      {/* ── Draft Preview + Edit ── */}
      {draft && (
        <div className="blt-sections">
          {/* ═══ Data Source Summary ═══ */}
          {draft.data_sources && draft.data_sources.length > 0 && (
            <div className="card blt-section">
              <div className="blt-section-header">
                <h3><IconDatabase /> Trạng thái nguồn dữ liệu</h3>
              </div>
              <div style={{ display: 'grid', gap: 8, padding: '4px 0' }}>
                {draft.data_sources.map((ds, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13 }}>
                    {(() => {
                      const m = ds.source === 'db'
                        ? { bg: '#16a34a1f', fg: '#0b7a3b', label: 'DB', icon: <IconDatabase /> }
                        : ds.source === 'manual'
                        ? { bg: '#0ea5e91f', fg: '#0369a1', label: 'Nhập tay', icon: <IconEdit /> }
                        : { bg: '#f59e0b22', fg: '#a96a00', label: 'Chưa quét', icon: <IconAlertTriangle /> };
                      return (
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                          padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                          background: m.bg, color: m.fg, minWidth: 72, justifyContent: 'center',
                        }}>
                          {m.icon} {m.label}
                        </span>
                      );
                    })()}
                    <span style={{ color: 'var(--text)', fontWeight: 500 }}>{ds.section}</span>
                    <span style={{ color: 'var(--muted)', fontSize: 12 }}>{ds.description}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {/* ═══ Section I: Giá CSTN thế giới (READ-ONLY) ═══ */}
          <div className="card blt-section">
            <div className="blt-section-header">
              <h3>I. Giá cao su thiên nhiên thế giới</h3>
              <div className="blt-section-meta">
                <span className="chip">Ngày: {draft.report_date}</span>
                {draft.world_prices.length > 0 ? (
                  <span className="chip"><IconCheck /> Dữ liệu thật</span>
                ) : (
                  <span className="chip warn"><IconAlertTriangle /> Chưa có dữ liệu</span>
                )}
                <Link className="chip" style={{ textDecoration: "none" }}
                  to="/quan-ly-so-lieu/bang-gia-san">
                  ↗ Bảng tính giá
                </Link>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Sàn</th>
                  <th>Mặt hàng</th>
                  <th>Đơn vị</th>
                  <th className="r">Giá ({draft.prev_date})</th>
                  <th className="r">Giá ({draft.report_date})</th>
                  <th className="r">+/−</th>
                  <th className="r">%</th>
                </tr>
              </thead>
              <tbody>
                {draft.world_prices.map((w, i) => (
                  <tr key={i}>
                    <td>{w.exchange}</td>
                    <td>{w.grade}</td>
                    <td>{w.unit}</td>
                    <td className="r">{fmt(w.price_prev)}</td>
                    <td className="r">{fmt(w.price_curr)}</td>
                    <td className={`r ${cls(w.change_abs)}`}>{fmtChg(w.change_abs)}</td>
                    <td className={`r ${cls(w.change_pct)}`}>{fmtPct(w.change_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ═══ Section II: Giá Physical (READ-ONLY) ═══ */}
          <div className="card blt-section">
            <div className="blt-section-header">
              <h3>II. Giá vật chất (Reuters / Physical)</h3>
              <div className="blt-section-meta">
                {draft.physical_prices.length === 0 ? (
                  <span className="chip warn"><IconAlertTriangle /> Không có giá vật chất</span>
                ) : draft.physical_prices.some((p) => p.price_curr != null) ? (
                  <span className="chip"><IconCheck /> Dữ liệu thật ({draft.physical_curr_label || draft.report_date})</span>
                ) : (
                  <span className="chip warn"><IconAlertTriangle /> Chưa có giá ngày {draft.physical_curr_label || draft.report_date}</span>
                )}
                <Link className="chip" style={{ textDecoration: "none" }}
                  to="/quan-ly-so-lieu/bang-gia-san">
                  ↗ Bảng tính giá
                </Link>
              </div>
            </div>
            {draft.physical_prices.length > 0 ? (
              <table>
                <thead>
                  <tr>
                    <th>Mặt hàng</th>
                    <th className="r">Giá ({draft.physical_prev_label || draft.prev_date})</th>
                    <th className="r">Giá ({draft.physical_curr_label || draft.report_date})</th>
                    <th className="r">+/−</th>
                    <th className="r">%</th>
                  </tr>
                </thead>
                <tbody>
                  {draft.physical_prices.map((p, i) => (
                    <tr key={i}>
                      <td>{p.grade}</td>
                      <td className="r">{fmt(p.price_prev)}</td>
                      <td className="r">{fmt(p.price_curr)}</td>
                      <td className={`r ${cls(p.change_abs)}`}>{fmtChg(p.change_abs)}</td>
                      <td className={`r ${cls(p.change_pct)}`}>{fmtPct(p.change_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="blt-hint">Không có giá vật chất giao dịch cho ngày {draft.report_date}.</div>
            )}
          </div>

          {/* ═══ Section III: Giá sàn VRG (READ-ONLY — từ Giá sàn Tập đoàn) ═══ */}
          <div className="card blt-section">
            <div className="blt-section-header">
              <h3>III. Giá trong nước — Giá sàn VRG</h3>
              <div className="blt-section-meta">
                {draft.vrg_floor_curr.some((x) => x.fob_usd != null || x.domestic_vnd != null) ? (
                  <span className="chip"><IconCheck /> Từ biểu giá Tập đoàn</span>
                ) : (
                  <span className="chip warn"><IconAlertTriangle /> Chưa có biểu giá</span>
                )}
                <Link className="chip" style={{ textDecoration: "none" }}
                  to="/quan-ly-so-lieu/gia-san-tap-doan">
                  ↗ Quản lý Giá sàn Tập đoàn
                </Link>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Chủng loại</th>
                  <th className="r">FOB (USD) — {draft.vrg_floor_prev_label?.replace(/\n/g, " ")}</th>
                  <th className="r">Nội địa (VNĐ) — {draft.vrg_floor_prev_label?.replace(/\n/g, " ")}</th>
                  <th className="r">FOB (USD) — {draft.vrg_floor_curr_label?.replace(/\n/g, " ")}</th>
                  <th className="r">Nội địa (VNĐ) — {draft.vrg_floor_curr_label?.replace(/\n/g, " ")}</th>
                </tr>
              </thead>
              <tbody>
                {draft.vrg_floor_curr
                  .map((item, i) => ({ item, prev: draft.vrg_floor_prev[i] }))
                  // Ẩn dòng không có giá ở cả 2 lần (vd SkimBlock chưa nhập).
                  .filter(({ item, prev }) =>
                    item.fob_usd != null || item.domestic_vnd != null ||
                    prev?.fob_usd != null || prev?.domestic_vnd != null)
                  .map(({ item, prev }) => (
                    <tr key={item.grade}>
                      <td>{item.grade}</td>
                      <td className="r">{fmt(prev?.fob_usd ?? null)}</td>
                      <td className="r">{fmt(prev?.domestic_vnd ?? null)}</td>
                      <td className="r">{fmt(item.fob_usd)}</td>
                      <td className="r">{fmt(item.domestic_vnd)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>

          {/* ═══ Section III.2: Giá mủ nguyên liệu (READ-ONLY — từ Quản lý số liệu) ═══ */}
          <div className="card blt-section">
            <div className="blt-section-header">
              <h3>III.2 Giá mủ nguyên liệu (giá thu mua mủ nước)</h3>
              <div className="blt-section-meta">
                {draft.raw_materials.some((rm) => rm.price != null) ? (
                  <span className="chip"><IconCheck /> Từ kho giá (source=vrg)</span>
                ) : (
                  <span className="chip warn"><IconAlertTriangle /> Chưa có giá thu mua</span>
                )}
                <Link className="chip" style={{ textDecoration: "none" }}
                  to="/quan-ly-so-lieu/gia-mu-nguyen-lieu">
                  ↗ Quản lý Giá mủ nguyên liệu
                </Link>
              </div>
            </div>
            <p style={{ color: "var(--muted)", fontSize: 12, margin: "0 0 8px" }}>
              Đơn vị: <b>đồng/độ TSC</b>. Gom theo <b>khu vực</b> (khoảng giá nếu nhiều đơn vị) — chỉ lấy giá <b>đúng ngày báo cáo</b>; đơn vị chưa gán khu vực không hiện.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Khu vực</th>
                  <th className="r">Giá thu mua (đồng/độ TSC)</th>
                </tr>
              </thead>
              <tbody>
                {draft.raw_materials.map((rm, i) => (
                  <tr key={i}>
                    <td>Khu vực {rm.region}</td>
                    <td className="r">{rm.price_text || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ═══ Section IV: Phân tích thị trường (EDITABLE) ═══ */}
          <div className="card blt-section blt-editable">
            <div className="blt-section-header">
              <h3>IV. Phân tích thị trường</h3>
              <div className="blt-section-meta">
                <span className="chip info"><IconEdit /> Chỉnh sửa được</span>
              </div>
            </div>

            <div className="blt-subsection">
              <h4>1. Tóm tắt giá sàn giao dịch <span className="chip info">Tự sinh · sửa được</span></h4>
              {draft.exchange_summary.length ? (
                draft.exchange_summary.map((line, i) => (
                  <textarea
                    key={i}
                    className="blt-textarea"
                    rows={2}
                    value={line}
                    placeholder="(sàn này chưa có dữ liệu — có thể nhập nhận định thủ công)"
                    onChange={(e) => updateExchange(i, e.target.value)}
                  />
                ))
              ) : (
                <div className="blt-hint">Chưa có dữ liệu giá sàn cho ngày này.</div>
              )}
              <div className="blt-hint" style={{ marginTop: 4 }}>
                Tự sinh từ giá đã quét — sửa tay rồi bấm “Lưu bản tin” sẽ giữ đúng nội dung đã sửa.
              </div>
            </div>

            <div className="blt-subsection">
              <h4>2. Giá Physical <span className="chip info">Tự sinh · sửa được</span></h4>
              <textarea
                className="blt-textarea"
                rows={3}
                value={draft.physical_summary}
                placeholder="(chưa có dữ liệu physical — có thể nhập thủ công)"
                onChange={(e) => updateField("physical_summary", e.target.value)}
              />
            </div>

            <div className="blt-subsection">
              <h4>3. Phân tích & nhận định</h4>
              {draft.market_analysis.map((para, i) => (
                <div key={i} className="blt-analysis-row">
                  <textarea
                    className="blt-textarea"
                    rows={3}
                    value={para}
                    onChange={(e) => updateAnalysis(i, e.target.value)}
                  />
                  <button
                    className="blt-rm-btn"
                    onClick={() => removeAnalysis(i)}
                    title="Xóa đoạn"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button className="btn blt-add-btn" onClick={addAnalysis}>
                  + Thêm đoạn phân tích
                </button>
                <button className="btn btn-primary" onClick={aiAnalyze} disabled={aiBusy}>
                  {aiBusy ? <><span className="spinner" /> Đang phân tích…</> : "Phân tích bằng AI"}
                </button>
              </div>
              <div className="blt-hint" style={{ marginTop: 4 }}>
                AI lấy tin từ vietnambiz.vn rồi viết các đoạn nhận định (cần đặt API key ở Quản trị → Cấu hình → AI).
              </div>
            </div>

            <div className="blt-subsection">
              <h4>4. Nguồn tin</h4>
              {draft.source_urls.map((url, i) => (
                <input
                  key={i}
                  type="text"
                  className="blt-input blt-source-url"
                  value={url}
                  onChange={(e) => {
                    const items = [...draft.source_urls];
                    items[i] = e.target.value;
                    updateField("source_urls", items);
                  }}
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
