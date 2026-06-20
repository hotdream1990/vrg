import { useCallback, useState } from "react";
import { Link } from "react-router-dom";

import type {
  BulletinDraft,
  RawMaterialRegion,
  VrgFloorItem,
} from "../../../lib/bulletin-client";
import {
  createDraft,
  generatePptx,
  updateDraft,
} from "../../../lib/bulletin-client";

import BulletinImageSettings from "../../bulletin/BulletinImageSettings";
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
  const [draft, setDraft] = useState<BulletinDraft | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [dateInput, setDateInput] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0, 10); // YYYY-MM-DD for <input type=date>
  });

  const dateStr = useCallback(() => {
    const [y, m, d] = dateInput.split("-");
    return `${d}-${m}-${y}`;
  }, [dateInput]);

  /* ── Actions ── */

  const handleCreate = async () => {
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
  };

  const handleSave = async () => {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateDraft(
        {
          vrg_floor_prev_label: draft.vrg_floor_prev_label,
          vrg_floor_curr_label: draft.vrg_floor_curr_label,
          vrg_floor_prev: draft.vrg_floor_prev,
          vrg_floor_curr: draft.vrg_floor_curr,
          raw_materials: draft.raw_materials,
          exchange_summary: draft.exchange_summary,
          physical_summary: draft.physical_summary,
          market_analysis: draft.market_analysis,
          source_urls: draft.source_urls,
        },
        dateStr()
      );
      setDraft(updated);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setError(null);
    try {
      await generatePptx(dateStr());
    } catch (e: any) {
      setError(`Xuất PPTX thất bại: ${e.message}`);
    } finally {
      setExporting(false);
    }
  };

  /* ── Inline edit helpers ── */

  const updateField = <K extends keyof BulletinDraft>(key: K, val: BulletinDraft[K]) =>
    setDraft((prev) => (prev ? { ...prev, [key]: val } : prev));

  const updateFloorItem = (
    which: "vrg_floor_prev" | "vrg_floor_curr",
    idx: number,
    field: keyof VrgFloorItem,
    val: string
  ) => {
    if (!draft) return;
    const items = [...draft[which]];
    items[idx] = { ...items[idx], [field]: val ? parseInt(val.replace(/,/g, ""), 10) : null };
    updateField(which, items);
  };

  const updateRawMaterial = (idx: number, field: keyof RawMaterialRegion, val: string) => {
    if (!draft) return;
    const items = [...draft.raw_materials];
    items[idx] = { ...items[idx], [field]: val };
    updateField("raw_materials", items);
  };

  const updateAnalysis = (idx: number, val: string) => {
    if (!draft) return;
    const items = [...draft.market_analysis];
    items[idx] = val;
    updateField("market_analysis", items);
  };

  const addAnalysis = () => {
    if (!draft) return;
    updateField("market_analysis", [...draft.market_analysis, ""]);
  };

  const removeAnalysis = (idx: number) => {
    if (!draft) return;
    updateField("market_analysis", draft.market_analysis.filter((_, i) => i !== idx));
  };

  /* ── Render ── */

  return (
    <div className="main">
      {/* Header */}
      <div className="page-title">
        <div>
          <Link to="/ban-tin" className="blt-back">← Danh sách bản tin</Link>
          <h2><IconClipboard /> Bản tin Thị trường Cao su Ngày</h2>
          <p>Tạo, xem trước và chỉnh sửa bản tin trước khi xuất PPTX</p>
        </div>
        <div className="actions">
          {draft && (
            <>
              <button className="btn" onClick={handleSave} disabled={saving}>
                {saving ? <span className="spinner" /> : <IconSave />} Lưu
              </button>
              <button className="btn btn-primary" onClick={handleExport} disabled={exporting}>
                {exporting ? <span className="spinner" /> : <IconDownload />} Xuất PPTX
              </button>
            </>
          )}
        </div>
      </div>

      {/* Date picker + Create */}
      <div className="blt-toolbar">
        <label className="blt-date-label">
          Ngày bản tin:
          <input
            type="date"
            className="blt-date-input"
            value={dateInput}
            onChange={(e) => setDateInput(e.target.value)}
          />
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
            <div className="card blt-section" style={{ background: '#0d1117', border: '1px solid #1e293b' }}>
              <div className="blt-section-header">
                <h3><IconDatabase /> Trạng thái nguồn dữ liệu</h3>
              </div>
              <div style={{ display: 'grid', gap: 8, padding: '4px 0' }}>
                {draft.data_sources.map((ds, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13 }}>
                    {(() => {
                      const m = ds.source === 'db'
                        ? { bg: '#064e3b', fg: '#6ee7b7', label: 'DB', icon: <IconDatabase /> }
                        : ds.source === 'manual'
                        ? { bg: '#1e3a5f', fg: '#93c5fd', label: 'Nhập tay', icon: <IconEdit /> }
                        : { bg: '#7f1d1d', fg: '#fca5a5', label: 'Chưa quét', icon: <IconAlertTriangle /> };
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
                    <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{ds.section}</span>
                    <span style={{ color: '#94a3b8', fontSize: 12 }}>{ds.description}</span>
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
                  <tr key={i} className={w.is_fake ? "blt-fake-row" : ""}>
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
              <h3>II. Giá vật chất (ANRPC / Physical)</h3>
              <div className="blt-section-meta">
                {draft.physical_prices.length > 0 ? (
                  <span className="chip"><IconCheck /> Dữ liệu thật</span>
                ) : (
                  <span className="chip warn"><IconAlertTriangle /> Chưa có dữ liệu</span>
                )}
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Mặt hàng</th>
                  <th className="r">Giá ({draft.prev_date})</th>
                  <th className="r">Giá ({draft.report_date})</th>
                  <th className="r">+/−</th>
                  <th className="r">%</th>
                </tr>
              </thead>
              <tbody>
                {draft.physical_prices.map((p, i) => (
                  <tr key={i} className={p.is_fake ? "blt-fake-row" : ""}>
                    <td>{p.grade}</td>
                    <td className="r">{fmt(p.price_prev)}</td>
                    <td className="r">{fmt(p.price_curr)}</td>
                    <td className={`r ${cls(p.change_abs)}`}>{fmtChg(p.change_abs)}</td>
                    <td className={`r ${cls(p.change_pct)}`}>{fmtPct(p.change_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ═══ Section III: Giá trong nước (EDITABLE) ═══ */}
          <div className="card blt-section blt-editable">
            <div className="blt-section-header">
              <h3>III. Giá trong nước — Giá sàn VRG</h3>
              <div className="blt-section-meta">
                <span className="chip info"><IconEdit /> Chỉnh sửa được</span>
              </div>
            </div>

            <div className="blt-floor-labels">
              <label>
                Label cột trước:
                <input
                  type="text"
                  className="blt-input"
                  value={draft.vrg_floor_prev_label}
                  onChange={(e) => updateField("vrg_floor_prev_label", e.target.value)}
                />
              </label>
              <label>
                Label cột mới:
                <input
                  type="text"
                  className="blt-input"
                  value={draft.vrg_floor_curr_label}
                  onChange={(e) => updateField("vrg_floor_curr_label", e.target.value)}
                />
              </label>
            </div>

            <table>
              <thead>
                <tr>
                  <th>Chủng loại</th>
                  <th className="r">FOB (USD) — Trước</th>
                  <th className="r">Nội địa (VNĐ) — Trước</th>
                  <th className="r">FOB (USD) — Mới</th>
                  <th className="r">Nội địa (VNĐ) — Mới</th>
                </tr>
              </thead>
              <tbody>
                {draft.vrg_floor_curr.map((item, i) => (
                  <tr key={i}>
                    <td>{item.grade}</td>
                    <td className="r">
                      <input
                        type="text"
                        className="blt-cell-input"
                        value={draft.vrg_floor_prev[i]?.fob_usd?.toLocaleString() ?? ""}
                        onChange={(e) => updateFloorItem("vrg_floor_prev", i, "fob_usd", e.target.value)}
                      />
                    </td>
                    <td className="r">
                      <input
                        type="text"
                        className="blt-cell-input"
                        value={draft.vrg_floor_prev[i]?.domestic_vnd?.toLocaleString() ?? ""}
                        onChange={(e) => updateFloorItem("vrg_floor_prev", i, "domestic_vnd", e.target.value)}
                      />
                    </td>
                    <td className="r">
                      <input
                        type="text"
                        className="blt-cell-input"
                        value={item.fob_usd?.toLocaleString() ?? ""}
                        onChange={(e) => updateFloorItem("vrg_floor_curr", i, "fob_usd", e.target.value)}
                      />
                    </td>
                    <td className="r">
                      <input
                        type="text"
                        className="blt-cell-input"
                        value={item.domestic_vnd?.toLocaleString() ?? ""}
                        onChange={(e) => updateFloorItem("vrg_floor_curr", i, "domestic_vnd", e.target.value)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ═══ Section III.2: Giá mủ nguyên liệu (EDITABLE) ═══ */}
          <div className="card blt-section blt-editable">
            <div className="blt-section-header">
              <h3>III.2 Giá mủ nguyên liệu</h3>
              <div className="blt-section-meta">
                <span className="chip info"><IconEdit /> Chỉnh sửa được</span>
              </div>
            </div>
            <div className="blt-raw-materials">
              {draft.raw_materials.map((rm, i) => (
                <div key={i} className="blt-rm-row">
                  <input
                    type="text"
                    className="blt-input blt-rm-region"
                    value={rm.region}
                    onChange={(e) => updateRawMaterial(i, "region", e.target.value)}
                    placeholder="Khu vực"
                  />
                  <input
                    type="text"
                    className="blt-input blt-rm-price"
                    value={rm.price_text}
                    onChange={(e) => updateRawMaterial(i, "price_text", e.target.value)}
                    placeholder="Giá (đ/độ TSC)"
                  />
                </div>
              ))}
            </div>
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
              <h4>1. Tóm tắt giá sàn giao dịch</h4>
              {draft.exchange_summary.map((line, i) => (
                <textarea
                  key={i}
                  className="blt-textarea"
                  rows={2}
                  value={line}
                  onChange={(e) => {
                    const items = [...draft.exchange_summary];
                    items[i] = e.target.value;
                    updateField("exchange_summary", items);
                  }}
                />
              ))}
            </div>

            <div className="blt-subsection">
              <h4>2. Giá Physical</h4>
              <textarea
                className="blt-textarea"
                rows={2}
                value={draft.physical_summary}
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
              <button className="btn blt-add-btn" onClick={addAnalysis}>
                + Thêm đoạn phân tích
              </button>
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
