import { BulbOutlined, FileTextOutlined, FormOutlined, SaveOutlined } from "@ant-design/icons";
import { App, Button } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  type CorrRow,
  type FloorChart,
  type FloorModel,
  type FloorPoint,
  type SuggestResult,
  DEFAULT_FLOOR_MODEL,
  FLOOR_MODELS,
  fetchFloorChart,
  fetchFloorCorrelation,
  fetchFloorPoints,
  fetchFloorSuggest,
} from "../../../lib/floor-suggest-client";
import { DRAFT_LIST_PATH, createDraft, draftPath } from "../../../lib/floor-proposal-client";
import { dmy, todayISO } from "../../../lib/date";
import { useAuth } from "../../auth/AuthContext";
import CorrelationChart from "../charts/CorrelationChart";
import DateInput from "../sections/DateInput";
import AdjustmentTable from "./components/AdjustmentTable";
import BacktestPanel from "./components/BacktestPanel";
import InventoryIndicator from "./components/InventoryIndicator";
import RecommendationRationale from "./components/RecommendationRationale";
import ScenarioMatrix from "./components/ScenarioMatrix";
import ToTrinhPreview from "./components/ToTrinhPreview";
import "../../bulletin/bulletin.css";

const GRADES = ["SVR CV 50", "SVR CV60", "SVR L", "SVR 3L Mix", "SVR 3L", "SVR 5S", "SVR 5",
  "SVR 10 Mix", "SVR 10 / CSR 10", "SVR 20 / CSR 20", "RSS 3", "RSS 1", "LATEX", "Skim Block"];

/** Màn Gợi ý điều chỉnh giá sàn: chọn 1 lần đã ban hành → đề xuất NÂNG/GIỮ/HẠ so lần trước,
 *  diễn giải căn cứ, kiểm định độ khớp (backtest) + tương quan chỉ số. */
export default function FloorSuggestPage() {
  const [points, setPoints] = useState<FloorPoint[]>([]);
  // Mặc định gợi ý cho NGÀY CỤ THỂ (hôm nay) theo dữ liệu mới nhất — chủ dự án chốt 24/09/2026.
  const [asOf, setAsOf] = useState(todayISO());
  const [mode, setMode] = useState<"issuance" | "custom">("custom");
  const [backtest, setBacktest] = useState(true);
  const [model, setModel] = useState<FloorModel>(DEFAULT_FLOOR_MODEL);
  const [grade, setGrade] = useState("SVR 10 / CSR 10");
  const [sug, setSug] = useState<SuggestResult | null>(null);
  const [chart, setChart] = useState<FloorChart | null>(null);
  const [corr, setCorr] = useState<CorrRow[]>([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [chartLoading, setChartLoading] = useState(false);
  const [showToTrinh, setShowToTrinh] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const { canEditCap } = useAuth();
  const { message } = App.useApp();
  const navigate = useNavigate();
  const canSaveDraft = canEditCap("floor_suggest");

  /** Tờ trình đang xem → bản nháp (server dựng phương án từ mô hình tại ngày này) → mở để sửa tay. */
  const saveAsDraft = async () => {
    setSavingDraft(true);
    try {
      const d = await createDraft({ source: "floor_suggest", as_of: asOf, model });
      navigate(draftPath(d.id));
    } catch (e) {
      message.error(e instanceof Error ? e.message : "Không lưu được bản nháp.");
    } finally {
      setSavingDraft(false);
    }
  };

  useEffect(() => {
    fetchFloorPoints().then(setPoints).catch((e) => setErr(e.message));
  }, []);

  const loadSuggest = useCallback(() => {
    if (!asOf) return;
    setLoading(true);
    fetchFloorSuggest(asOf, model, backtest).then(setSug)
      .catch((e) => setErr(e.message)).finally(() => setLoading(false));
  }, [asOf, model, backtest]);
  useEffect(() => { loadSuggest(); }, [loadSuggest]);

  useEffect(() => {
    setChartLoading(true);
    Promise.all([
      fetchFloorChart(grade).then(setChart),
      fetchFloorCorrelation(grade).then(setCorr),
    ]).catch((e) => setErr(e.message)).finally(() => setChartLoading(false));
  }, [grade]);

  const markIndex = useMemo(() => (chart ? chart.labels.indexOf(asOf) : -1), [chart, asOf]);
  const focal = useMemo(() => sug?.items.find((i) => i.grade === grade), [sug, grade]);

  // Nhãn lần ban hành theo TEXT (tiêu đề tự đặt) + ngày phát hành — không dùng số lần nội bộ.
  const pointLabel = (p: FloorPoint) => {
    const t = p.title?.trim();
    const meaningful = t && t !== `Lần ${p.lan}`; // bỏ tiêu đề mặc định = số lần nội bộ
    return meaningful ? `${t} · ${dmy(p.as_of)}` : dmy(p.as_of);
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><BulbOutlined style={{ marginRight: 8 }} />Gợi ý điều chỉnh giá sàn</h2>
          <p>Mô hình hồi quy trên giá mủ nước và rổ chỉ số thị trường (MRB SMR20 · SGX TSR20 · SHFE · OSE RSS3) đề xuất
            NÂNG/GIỮ/HẠ giá sàn so với lần ban hành liền trước: mức đề xuất = giá sàn lần trước + mức thay đổi của mô hình
            từ đó tới nay, làm tròn theo bước ban hành, kèm diễn giải căn cứ và độ tin cậy.
            Chọn <b>một ngày cụ thể</b> để gợi ý giá sàn mới theo dữ liệu hiện có, hoặc 1 lần đã ban hành để đối chiếu.</p>
        </div>
      </div>
      {err && <div className="blt-error">{err}</div>}
      {sug?.error && <div className="blt-error">{sug.error}</div>}

      <div className="card" style={{ display: "flex", gap: 18, flexWrap: "wrap", alignItems: "center" }}>
        <label className="blt-date-label">Chế độ:
          <select className="blt-date-input" value={mode} onChange={(e) => {
            const m = e.target.value as "issuance" | "custom";
            setMode(m);
            if (m === "issuance") { if (points[0]) setAsOf(points[0].as_of); }
            else setAsOf(todayISO());
          }}>
            <option value="custom">Ngày cụ thể (gợi ý mới)</option>
            <option value="issuance">Lần đã ban hành</option>
          </select>
        </label>
        {mode === "issuance" ? (
          <label className="blt-date-label">Lần ban hành:
            <select className="blt-date-input" value={asOf} onChange={(e) => setAsOf(e.target.value)}>
              {points.map((p) => <option key={p.as_of} value={p.as_of}>{pointLabel(p)}</option>)}
            </select>
          </label>
        ) : (
          <label className="blt-date-label">Ngày gợi ý:
            <DateInput value={asOf} onChange={setAsOf} />
          </label>
        )}
        <label className="blt-date-label">Mô hình:
          <select className="blt-date-input" value={model} onChange={(e) => setModel(e.target.value as FloorModel)}>
            {FLOOR_MODELS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </label>
        {mode === "issuance" && (
          <label className="blt-date-label" style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={backtest} onChange={(e) => setBacktest(e.target.checked)} />
            Backtest (chỉ dùng data trước lần này)
          </label>
        )}
        {loading ? (
          <span className="chip" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span className="spinner" /> Đang tính toán theo dữ liệu mới…
          </span>
        ) : sug && !sug.error ? (
          <span className="chip">
            {sug.is_issuance === false ? "Ngày cụ thể · so với lần " + (sug.prev_as_of ?? "—") + " · " : ""}
            Biến: {sug.feats.join(" · ") || "—"} · fit {sug.n_train} lần
            {(model === "v1i" || model === "v1f") && sug.n_train === 0
              && ` · Chưa chạy được: cần thêm lần ban hành có tồn kho ngày (có từ ${dmy(sug.inventory_start)})`}
          </span>
        ) : null}
        <Button icon={<FormOutlined />} style={{ marginLeft: "auto" }} onClick={() => navigate(DRAFT_LIST_PATH)}>
          Quy trình giá sàn
        </Button>
        <button
          onClick={() => setShowToTrinh(true)}
          disabled={!asOf}
          style={{ display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer",
            background: "var(--accent, #16a34a)", color: "#fff", border: "none", borderRadius: 8,
            padding: "8px 16px", fontWeight: 600 }}
        >
          <FileTextOutlined /> Xem &amp; xuất tờ trình
        </button>
      </div>

      <div style={{ opacity: loading ? 0.45 : 1, pointerEvents: loading ? "none" : "auto", transition: "opacity .2s" }} aria-busy={loading}>
        <InventoryIndicator inv={sug?.inventory} lean={sug?.inventory_lean} start={sug?.inventory_start} />

        <AdjustmentTable items={sug?.items ?? []} focus={grade} onFocus={setGrade} />

        <RecommendationRationale
          item={focal}
          prevAsOf={sug?.prev_as_of ?? null}
          basketChangePct={sug?.basket_change_pct ?? null}
          drivers={sug?.drivers ?? []}
          inventoryLean={sug?.inventory_lean}
        />
      </div>

      {asOf && <ScenarioMatrix asOf={asOf} model={model} />}

      <BacktestPanel grade={grade} model={model} onModel={setModel} />

      <div className="card">
        <div className="card-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>Tương quan giá sàn ↔ chỉ số (chuẩn hoá base-100)</h3>
          <select className="blt-date-input" value={grade} onChange={(e) => setGrade(e.target.value)}>
            {GRADES.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
        <div style={{ height: 340, position: "relative", opacity: chartLoading ? 0.45 : 1, transition: "opacity .2s" }}>
          {chartLoading && (
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
              gap: 8, color: "var(--muted)", zIndex: 2 }}>
              <span className="spinner" /> Đang tải biểu đồ…
            </div>
          )}
          {chart && chart.labels.length > 0
            ? <CorrelationChart labels={chart.labels} series={chart.series} markIndex={markIndex} />
            : chartLoading ? null : <div className="scan-empty">Chưa có dữ liệu.</div>}
        </div>
        <p style={{ fontSize: 12, color: "var(--muted)" }}>Chấm to = lần đang chọn. Đường xanh đậm = giá sàn {grade}.</p>
      </div>

      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <div style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 8 }}>
          <b>Hệ số tương quan — {grade}</b> (Pearson, mức giá)
          {chartLoading && <span className="spinner" />}
        </div>
        <table style={{ fontSize: 13, opacity: chartLoading ? 0.45 : 1, transition: "opacity .2s" }}>
          <thead><tr><th>Chỉ số</th><th className="r">Tương quan (r)</th><th className="r">Số điểm</th></tr></thead>
          <tbody>
            {corr.map((c) => (
              <tr key={c.index}>
                <td>{c.index}</td>
                <td className="r" style={{ fontWeight: 600, color: Math.abs(c.r) >= 0.8 ? "#16a34a" : Math.abs(c.r) >= 0.6 ? "#ca8a04" : "var(--muted)" }}>{c.r.toFixed(3)}</td>
                <td className="r" style={{ color: "var(--muted)" }}>{c.n}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showToTrinh && asOf && (
        <ToTrinhPreview asOf={asOf} model={model} onClose={() => setShowToTrinh(false)}
          extraActions={canSaveDraft && (
            <Button icon={<SaveOutlined />} loading={savingDraft} onClick={saveAsDraft}>Lưu thành bản nháp</Button>
          )} />
      )}
    </div>
  );
}
