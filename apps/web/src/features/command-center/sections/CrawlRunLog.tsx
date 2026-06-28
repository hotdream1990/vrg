import { useEffect, useState } from "react";

import { type CrawlRun, fetchCrawlRuns } from "../../../lib/api-client";

const STATUS: Record<string, { label: string; cls: string }> = {
  ok: { label: "Thành công", cls: "ok" },
  error: { label: "Lỗi", cls: "err" },
  empty: { label: "Không có dữ liệu", cls: "warn" },
  running: { label: "Đang chạy", cls: "warn" },
};

function duration(start: string, end: string | null): string {
  if (!end) return "—";
  const s = (new Date(end).getTime() - new Date(start).getTime()) / 1000;
  return s < 60 ? `${s.toFixed(1)}s` : `${(s / 60).toFixed(1)} phút`;
}

/** Nhật ký các lần quét giá (thủ công + cron), đọc từ meta_crawl_run. */
export default function CrawlRunLog({ reloadKey }: { reloadKey?: number }) {
  const [runs, setRuns] = useState<CrawlRun[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchCrawlRuns(20)
      .then((r) => setRuns(r.runs))
      .catch((e) => setErr(String(e)));
  }, [reloadKey]);

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <div className="card-head">
        <div>
          <h3>Nhật ký quét giá</h3>
          <div className="sub">20 lần quét gần nhất · quét thủ công &amp; theo lịch (cron)</div>
        </div>
      </div>
      {err ? (
        <div className="scan-empty">Không tải được nhật ký: {err}</div>
      ) : runs.length === 0 ? (
        <div className="scan-empty">Chưa có lần quét nào.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Thời gian</th>
              <th>Nguồn</th>
              <th>Trạng thái</th>
              <th style={{ textAlign: "right" }}>Bản ghi</th>
              <th>Thời lượng</th>
              <th>Ghi chú</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => {
              const st = STATUS[r.status] ?? { label: r.status, cls: "warn" };
              return (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>{new Date(r.started_at).toLocaleString("vi-VN")}</td>
                  <td>{r.sources ?? "—"}</td>
                  <td><span className={`db-badge ${st.cls}`}>{st.label}</span></td>
                  <td style={{ textAlign: "right" }}>{r.rows}</td>
                  <td>{duration(r.started_at, r.finished_at)}</td>
                  <td style={{ color: "var(--muted)", fontSize: 12 }} title={r.error ?? ""}>
                    {r.error ? r.error.slice(0, 70) : ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
