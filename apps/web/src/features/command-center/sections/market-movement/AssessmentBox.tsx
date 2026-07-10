import { RobotOutlined } from "@ant-design/icons";
import { useState } from "react";

import { type AssessmentResult, generateAssessment } from "../../../../lib/market-movement-client";
import { buildSummaries } from "./summary";

/** Box "Nhận định chung (AI)" — bấm để gom số liệu các nhóm → AI viết nhận định từng nhóm + tổng thể.
 *  Không lưu: mỗi lần bấm sinh mới theo số liệu hiện tại. */
export default function AssessmentBox() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState<AssessmentResult | null>(null);

  const run = async () => {
    setBusy(true); setErr("");
    try {
      const groups = await buildSummaries();
      setResult(await generateAssessment(groups));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Không tạo được nhận định.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card" id="sec-nhandinh" style={{ marginBottom: 18 }}>
      <div className="card-head">
        <div>
          <h3><RobotOutlined style={{ marginRight: 8, color: "var(--accent)" }} />Nhận định chung (AI)</h3>
          <div className="sub">Tổng hợp xu hướng các nhóm số liệu bên dưới — mỗi nhóm 1 dòng + đánh giá tổng thể.</div>
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
        </div>
      )}
    </div>
  );
}
