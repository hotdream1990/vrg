import { CheckCircleOutlined, ExclamationCircleOutlined, SyncOutlined } from "@ant-design/icons";
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

type Chip = { key: string; label: string; ok: boolean; title: string };
type Result = { tone: "ok" | "warn" | "err"; summary: string; chips: Chip[]; notes: string[] };

const build = (r: ScanResult): Result => {
  const errs = r.sources.filter((s) => s.status === "error");
  const oks = r.sources.filter((s) => s.status !== "error");
  const chips: Chip[] = r.sources.map((s: SourceStatus) => ({
    key: s.source,
    label: s.status === "error"
      ? `${friendly(s.source)} · ${isNetErr(s.note) ? "lỗi mạng" : "lỗi"}`
      : `${friendly(s.source)} · ${s.count}`,
    ok: s.status !== "error",
    title: s.status === "error" ? (s.note || "Lỗi không xác định") : (s.note || `${s.count} bản ghi`),
  }));
  // Nguồn quét OK nhưng CÓ ghi chú (sàn nghỉ, No Trading, phải lấy phiên cũ hơn vì báo cáo
  // hôm nay chưa đăng) — phải hiện thành chữ, đừng để chuyên viên tự đoán vì sao số không đổi.
  const notes = oks.filter((s) => s.note).map((s) => `${friendly(s.source)}: ${s.note}`);
  if (errs.length === 0)
    return { tone: "ok", summary: `Đã ghi ${r.persisted} bản ghi · ${oks.length}/${r.sources.length} nguồn OK`, chips, notes };
  if (oks.length > 0)
    return { tone: "warn", summary: `Đã ghi ${r.persisted} bản ghi · ${oks.length}/${r.sources.length} nguồn OK, ${errs.length} lỗi`, chips, notes };
  return { tone: "err", summary: "Không quét được nguồn nào", chips, notes };
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
      setResult({ tone: "err", summary: String(e).slice(0, 90), chips: [], notes: [] });
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
          {result.notes.map((n) => (
            <span key={n} style={{ width: "100%", color: "var(--muted)", fontSize: 12 }}>{n}</span>
          ))}
        </>
      )}
    </span>
  );
}
