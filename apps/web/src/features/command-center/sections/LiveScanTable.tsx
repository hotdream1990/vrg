import { type LatestRow, type ScanResult } from "../../../lib/api-client";
import { dmy } from "../../../lib/date";

/** Bảng chi tiết giá đã lưu + chip trạng thái nguồn + note nguồn chưa có data. */
export default function LiveScanTable({
  latest,
  scanInfo,
  missing,
}: {
  latest: LatestRow[];
  scanInfo: ScanResult | null;
  missing: string[];
}) {
  return (
    <>
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
              <td>{dmy(r.as_of)}</td>
            </tr>
          ))}
        </tbody>
      </table>

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
    </>
  );
}
