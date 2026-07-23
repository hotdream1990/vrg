import {
  CheckCircleFilled,
  DatabaseOutlined,
  ExclamationCircleFilled,
  RobotOutlined,
} from "@ant-design/icons";
import { useState } from "react";

import { dmy } from "../../../../lib/date";
import {
  type AssessmentResult,
  type GroupMeta,
  generateAssessment,
} from "../../../../lib/market-movement-client";
import TrendBox from "./TrendBox";
import { buildSummaries } from "./summary";

/** Box "Nhận định chung (AI)" — bấm để gom số liệu các nhóm → AI viết nhận định từng nhóm + tổng thể.
 *  Không lưu: mỗi lần bấm sinh mới theo số liệu hiện tại.
 *  Kèm khối "Nguồn & phạm vi dữ liệu" để minh bạch: AI chỉ dùng số liệu hệ thống dưới đây, không bịa. */
export default function AssessmentBox() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [metas, setMetas] = useState<GroupMeta[]>([]);
  const [showRaw, setShowRaw] = useState(false);

  const run = async () => {
    setBusy(true); setErr("");
    try {
      const groups = await buildSummaries();
      setMetas(groups);
      setResult(await generateAssessment(groups));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Không tạo được nhận định.");
    } finally {
      setBusy(false);
    }
  };

  const okCount = metas.filter((m) => m.ok).length;
  const overallLatest = metas.map((m) => m.latest).filter((x): x is string => !!x).sort().at(-1);

  return (
    <div className="card" id="sec-nhandinh" style={{ marginBottom: 18 }}>
      <div className="card-head">
        <div>
          <h3><RobotOutlined style={{ marginRight: 8, color: "var(--accent)" }} />Nhận định chung (AI)</h3>
          <div className="sub">Tổng hợp xu hướng các nhóm số liệu bên dưới — mỗi nhóm 1 dòng + đánh giá tổng thể + gợi ý xu hướng ngắn hạn.</div>
        </div>
        <button className="btn btn-primary" onClick={run} disabled={busy}>
          {busy ? <><span className="spinner" /> Đang tạo…</> : result ? "Tạo lại" : "Tạo nhận định bằng AI"}
        </button>
      </div>

      {err && <div className="blt-error" style={{ marginTop: 12 }}>{err}</div>}

      {!result && !err && (
        <div className="scan-empty">
          Bấm <b>“Tạo nhận định bằng AI”</b> để tổng hợp tình hình các nhóm số liệu.
          <div style={{ fontSize: 12, marginTop: 6 }}>
            Cần đặt API key ở Quản trị → Cấu hình hệ thống → tab AI.
          </div>
        </div>
      )}

      {result && (
        <div style={{ marginTop: 12 }}>
          {result.overall && (
            <div style={{
              background: "#16AF6712", border: "1px solid #16AF6733", borderRadius: 8,
              padding: "12px 14px", marginBottom: 12, lineHeight: 1.55, color: "var(--text)",
            }}>
              <b style={{ color: "var(--accent-2)" }}>Tổng thể. </b>{result.overall}
            </div>
          )}
          {result.trend && <TrendBox trend={result.trend} />}
          <div>
            {result.groups.map((g) => (
              <div key={g.key} style={{
                display: "grid", gridTemplateColumns: "minmax(160px, 220px) 1fr", gap: 12,
                padding: "9px 0", borderBottom: "1px solid var(--line)", alignItems: "start",
              }}>
                <div style={{ fontWeight: 600, color: "var(--text)" }}>{g.label}</div>
                <div style={{ color: "var(--text)", lineHeight: 1.5 }}>{g.assessment || "—"}</div>
              </div>
            ))}
          </div>
          <div className="sub" style={{ marginTop: 10 }}>
            Tạo lúc {result.generated_at} · AI tổng hợp từ số liệu hệ thống — cần rà soát trước khi trình.
          </div>

          {metas.length > 0 && <DataProvenance metas={metas} okCount={okCount} latest={overallLatest} showRaw={showRaw} onToggleRaw={() => setShowRaw((v) => !v)} />}
        </div>
      )}
    </div>
  );
}

/** Khối minh bạch: mỗi nhóm nạp dữ liệu gì, khoảng ngày nào, có số liệu thật không + xem được dữ liệu thô đưa vào AI. */
function DataProvenance({
  metas, okCount, latest, showRaw, onToggleRaw,
}: {
  metas: GroupMeta[]; okCount: number; latest?: string; showRaw: boolean; onToggleRaw: () => void;
}) {
  return (
    <div style={{ marginTop: 12, border: "1px solid var(--line)", borderRadius: 8, padding: "12px 14px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 6 }}>
        <b style={{ color: "var(--text)", fontSize: 13 }}>
          <DatabaseOutlined style={{ marginRight: 6, color: "var(--accent)" }} />Nguồn &amp; phạm vi dữ liệu AI đã dùng
        </b>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          {okCount}/{metas.length} nhóm có số liệu{latest ? ` · mới nhất ${dmy(latest)}` : ""}
        </span>
      </div>
      <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 8 }}>
        AI chỉ dùng số liệu <b>phiên/kỳ mới nhất</b> đối chiếu kỳ liền trước (đã tính sẵn %thay đổi) —
        không phân tích cả kho lịch sử, không truy cập nguồn ngoài, không bịa thêm.
      </div>

      {metas.map((m) => (
        <div key={m.key} style={{
          display: "grid", gridTemplateColumns: "minmax(150px, 210px) 1fr minmax(140px, auto)",
          gap: 10, padding: "7px 0", borderTop: "1px solid var(--line)", alignItems: "start", fontSize: 12.5,
        }}>
          <div style={{ fontWeight: 600, color: "var(--text)" }}>
            {m.ok
              ? <CheckCircleFilled style={{ color: "var(--accent)", marginRight: 6 }} />
              : <ExclamationCircleFilled style={{ color: "var(--warn)", marginRight: 6 }} />}
            {m.label}
          </div>
          <div style={{ color: "var(--muted)", lineHeight: 1.45 }}>{m.source}</div>
          <div style={{ color: m.ok ? "var(--text)" : "var(--warn)", textAlign: "right", lineHeight: 1.45 }}>
            {m.ok ? m.range : "Chưa đủ dữ liệu"}
          </div>
        </div>
      ))}

      <button className="btn" style={{ marginTop: 10, fontSize: 12, padding: "6px 12px" }} onClick={onToggleRaw}>
        {showRaw ? "Ẩn dữ liệu thô" : "Xem dữ liệu thô đưa vào AI"}
      </button>
      {showRaw && (
        <div style={{ marginTop: 8 }}>
          {metas.map((m) => (
            <div key={m.key} style={{ padding: "7px 0", borderTop: "1px solid var(--line)" }}>
              <div style={{ fontWeight: 600, fontSize: 12, color: "var(--text)" }}>{m.label}</div>
              <div style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{m.summary}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
