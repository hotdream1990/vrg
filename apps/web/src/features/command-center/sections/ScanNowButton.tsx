import { CheckCircleOutlined, ExclamationCircleOutlined, SyncOutlined, WarningOutlined } from "@ant-design/icons";
import { useState } from "react";

import { type ScanResult, type SourceStatus, scanPrices } from "../../../lib/api-client";

type Props = {
  /** Mã nguồn truyền cho /scan (vd "all", "fx", "shfe,tocom,lgm,sgx"). */
  source: string;
  label: string;
  /** Gọi lại sau khi quét xong để trang nạp lại dữ liệu. */
  onDone?: () => void;
};

/** Tên hiển thị thân thiện cho từng mã nguồn crawler. */
const NAMES: Record<string, string> = { shfe: "SHFE", tocom: "OSE", sgx: "SGX", lgm: "MRB", fx: "Tỷ giá" };
const friendly = (s: string) => NAMES[s] ?? s.toUpperCase();

/** Lỗi tầng mạng (không kết nối được nguồn) → hiển thị "lỗi mạng" cho dễ hiểu. */
const isNetErr = (note?: string | null) =>
  !!note && /route to host|EHOSTUNREACH|Errno 113|timed out|timeout|connection|getaddrinfo|resolve/i.test(note);

/** Nhãn trạng thái nguồn không OK (khớp Status của crawler). */
const STATUS_LABEL: Record<string, string> = { empty: "không có dữ liệu", blocked: "bị chặn", error: "lỗi" };

type Chip = { key: string; label: string; ok: boolean; title: string };
type Result = { tone: "ok" | "warn" | "err"; summary: string; chips: Chip[]; notes: string[]; warnings: string[] };

const build = (r: ScanResult): Result => {
  // Cảnh báo do SERVER tổng hợp (nguồn lỗi · ghi chú lỗi của nguồn · tỷ giá quá cũ) — nguồn quét
  // "OK" mà thiếu cặp tỷ giá cũng phải hiện, không được xanh (sự cố 03–13/09/2026).
  const warnings = r.warnings ?? [];
  const warnedBy = (s: SourceStatus) => warnings.some((w) => w.startsWith(`${friendly(s.source)}:`));
  const bad = r.sources.filter((s) => s.status !== "ok");
  const oks = r.sources.filter((s) => s.status === "ok");
  const chips: Chip[] = r.sources.map((s: SourceStatus) => ({
    key: s.source,
    label: s.status === "ok"
      ? `${friendly(s.source)} · ${s.count}`
      : `${friendly(s.source)} · ${isNetErr(s.note) ? "lỗi mạng" : (STATUS_LABEL[s.status] ?? s.status)}`,
    ok: s.status === "ok" && !warnedBy(s),
    title: s.note || (s.status === "ok" ? `${s.count} bản ghi` : "Lỗi không xác định"),
  }));
  // Nguồn quét OK nhưng CÓ ghi chú thông tin (sàn nghỉ, No Trading, lấy phiên cũ hơn vì báo cáo
  // hôm nay chưa đăng) — hiện thành chữ, đừng để chuyên viên tự đoán vì sao số không đổi.
  const notes = oks.filter((s) => s.note && !warnedBy(s)).map((s) => `${friendly(s.source)}: ${s.note}`);
  const base = `Đã ghi ${r.persisted} bản ghi · ${oks.length}/${r.sources.length} nguồn OK`;
  if (r.sources.length > 0 && oks.length === 0)
    return { tone: "err", summary: "Không quét được nguồn nào", chips, notes, warnings };
  if (r.status === "error")
    return { tone: "err", summary: `Không ghi được kho giá (${r.db})`, chips, notes, warnings };
  if (bad.length > 0 || warnings.length > 0 || r.status === "warning")
    return { tone: "warn", summary: `${base} · ${warnings.length || bad.length} cảnh báo`, chips, notes, warnings };
  return { tone: "ok", summary: base, chips, notes, warnings };
};

/** Nút "Quét ngay" theo nguồn — báo rõ nguồn nào OK / nguồn nào lỗi (không đánh đồng lỗi cả cụm). */
export default function ScanNowButton({ source, label, onDone }: Props) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  const run = async () => {
    setBusy(true);
    setResult(null);
    try {
      const r = await scanPrices(source);
      setResult(build(r));
      if (r.persisted > 0) onDone?.();  // có bản ghi mới → nạp lại lưới, dù 1 nguồn lỗi
    } catch (e) {
      setResult({ tone: "err", summary: String(e).slice(0, 90), chips: [], notes: [], warnings: [] });
    } finally {
      setBusy(false);
    }
  };

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
      <button className="btn" onClick={run} disabled={busy}>
        {busy ? <><span className="spinner" /> Đang quét…</> : <><SyncOutlined /> {label}</>}
      </button>
      {result && (
        <>
          <span className={`db-badge ${result.tone}`}>{result.summary}</span>
          {result.chips.map((c) => (
            <span key={c.key} className={`src-chip ${c.ok ? "ok" : "bad"}`} title={c.title}>
              {c.ok ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />} {c.label}
            </span>
          ))}
          {result.warnings.map((w) => (
            <span key={w} style={{ width: "100%", color: "#a96a00", fontSize: 12 }}>
              <WarningOutlined /> {w}
            </span>
          ))}
          {result.notes.map((n) => (
            <span key={n} style={{ width: "100%", color: "var(--muted)", fontSize: 12 }}>{n}</span>
          ))}
        </>
      )}
    </span>
  );
}
