import { BulbOutlined, FileTextOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  type CorrRow,
  type FloorChart,
  type FloorModel,
  type FloorPoint,
  type SuggestResult,
  fetchFloorChart,
  fetchFloorCorrelation,
  fetchFloorPoints,
  fetchFloorSuggest,
} from "../../../lib/floor-suggest-client";
import CorrelationChart from "../charts/CorrelationChart";
import AdjustmentTable from "./components/AdjustmentTable";
import BacktestPanel from "./components/BacktestPanel";
import RecommendationRationale from "./components/RecommendationRationale";
import ScenarioMatrix from "./components/ScenarioMatrix";
import ToTrinhPreview from "./components/ToTrinhPreview";
import "../../bulletin/bulletin.css";

const GRADES = ["SVR CV 50", "SVR CV60", "SVR L", "SVR 3L Mix", "SVR 3L", "SVR 5S", "SVR 5",
  "SVR 10 Mix", "SVR 10", "SVR 20", "RSS 3", "RSS 1", "LATEX"];

/** Màn Gợi ý điều chỉnh giá sàn: chọn 1 lần đã ban hành → đề xuất NÂNG/GIỮ/HẠ so lần trước,
 *  diễn giải căn cứ, kiểm định độ khớp (backtest) + tương quan chỉ số. */
export default function FloorSuggestPage() {
  const [points, setPoints] = useState<FloorPoint[]>([]);
  const [asOf, setAsOf] = useState("");
  const [mode, setMode] = useState<"issuance" | "custom">("issuance");
  const [backtest, setBacktest] = useState(true);
  const [model, setModel] = useState<FloorModel>("v1");
  const [grade, setGrade] = useState("SVR 10");
  const [sug, setSug] = useState<SuggestResult | null>(null);
  const [chart, setChart] = useState<FloorChart | null>(null);
  const [corr, setCorr] = useState<CorrRow[]>([]);
  const [err, setErr] = useState("");
  const [showToTrinh, setShowToTrinh] = useState(false);

  useEffect(() => {
    fetchFloorPoints().then((p) => { setPoints(p); if (p[0]) setAsOf(p[0].as_of); })
      .catch((e) => setErr(e.message));
  }, []);

  const loadSuggest = useCallback(() => {
    if (!asOf) return;
    fetchFloorSuggest(asOf, model, backtest).then(setSug).catch((e) => setErr(e.message));
  }, [asOf, model, backtest]);
  useEffect(() => { loadSuggest(); }, [loadSuggest]);

  useEffect(() => {
    fetchFloorChart(grade).then(setChart).catch((e) => setErr(e.message));
    fetchFloorCorrelation(grade).then(setCorr).catch((e) => setErr(e.message));
  }, [grade]);

  const markIndex = useMemo(() => (chart ? chart.labels.indexOf(asOf) : -1), [chart, asOf]);
  const focal = useMemo(() => sug?.items.find((i) => i.grade === grade), [sug, grade]);

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><BulbOutlined style={{ marginRight: 8 }} />Gợi ý điều chỉnh giá sàn</h2>
          <p>Mô hình hồi quy theo rổ chỉ số thị trường (MRB SMR20 · SGX TSR20 · SHFE · OSE RSS3) đề xuất
            NÂNG/GIỮ/HẠ giá sàn so với lần ban hành liền trước, kèm diễn giải căn cứ và độ tin cậy.
            Chọn 1 lần đã ban hành để đối chiếu, hoặc <b>một ngày bất kỳ</b> để gợi ý giá sàn mới theo dữ liệu hiện có.</p>
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
            else setAsOf(new Date().toISOString().slice(0, 10));
          }}>
            <option value="issuance">Lần đã ban hành</option>
            <option value="custom">Ngày bất kỳ (gợi ý mới)</option>
          </select>
        </label>
        {mode === "issuance" ? (
          <label className="blt-date-label">Lần ban hành:
            <select className="blt-date-input" value={asOf} onChange={(e) => setAsOf(e.target.value)}>
              {points.map((p) => <option key={p.as_of} value={p.as_of}>Lần {p.lan} · {p.as_of}</option>)}
            </select>
          </label>
        ) : (
          <label className="blt-date-label">Ngày gợi ý:
            <input type="date" className="blt-date-input" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
          </label>
        )}
        <label className="blt-date-label">Mô hình:
          <select className="blt-date-input" value={model} onChange={(e) => setModel(e.target.value as FloorModel)}>
            <option value="v1">Rổ 4 futures (khuyến nghị)</option>
            <option value="v1i">Rổ + Tồn kho tổng (thử nghiệm)</option>
            <option value="v1f">Rổ + Tồn kho tự do (thử nghiệm)</option>
            <option value="v2">Đa biến + mủ nước (đối chiếu)</option>
          </select>
        </label>
        {mode === "issuance" && (
          <label className="blt-date-label" style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={backtest} onChange={(e) => setBacktest(e.target.checked)} />
            Backtest (chỉ dùng data trước lần này)
          </label>
        )}
        {sug && !sug.error && (
          <span className="chip">
            {sug.is_issuance === false ? "Ngày bất kỳ · so với lần " + (sug.prev_as_of ?? "—") + " · " : ""}
            Biến: {sug.feats.join(" · ") || "—"} · fit {sug.n_train} lần
          </span>
        )}
        <button
          onClick={() => setShowToTrinh(true)}
          disabled={!asOf}
          style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer",
            background: "var(--accent, #16a34a)", color: "#fff", border: "none", borderRadius: 8,
            padding: "8px 16px", fontWeight: 600 }}
        >
          <FileTextOutlined /> Xem &amp; xuất tờ trình
        </button>
      </div>

      <AdjustmentTable items={sug?.items ?? []} focus={grade} onFocus={setGrade} />

      <RecommendationRationale
        item={focal}
        prevAsOf={sug?.prev_as_of ?? null}
        basketChangePct={sug?.basket_change_pct ?? null}
        drivers={sug?.drivers ?? []}
      />

      {asOf && <ScenarioMatrix asOf={asOf} model={model} />}

      <BacktestPanel grade={grade} />

      <div className="card">
        <div className="card-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>Tương quan giá sàn ↔ chỉ số (chuẩn hoá base-100)</h3>
          <select className="blt-date-input" value={grade} onChange={(e) => setGrade(e.target.value)}>
            {GRADES.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
        <div style={{ height: 340 }}>
          {chart && chart.labels.length > 0
            ? <CorrelationChart labels={chart.labels} series={chart.series} markIndex={markIndex} />
            : <div className="scan-empty">Chưa có dữ liệu.</div>}
        </div>
        <p style={{ fontSize: 12, color: "var(--muted)" }}>Chấm to = lần đang chọn. Đường xanh đậm = giá sàn {grade}.</p>
      </div>

      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <div style={{ padding: "12px 16px" }}><b>Hệ số tương quan — {grade}</b> (Pearson, mức giá)</div>
        <table style={{ fontSize: 13 }}>
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
        <ToTrinhPreview asOf={asOf} model={model} onClose={() => setShowToTrinh(false)} />
      )}
    </div>
  );
}
