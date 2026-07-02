import { SyncOutlined } from "@ant-design/icons";
import { useState } from "react";

import { scanPrices } from "../../../lib/api-client";

type Props = {
  /** Mã nguồn truyền cho /scan (vd "all", "fx", "shfe,tocom,lgm,sgx"). */
  source: string;
  label: string;
  /** Gọi lại sau khi quét xong để trang nạp lại dữ liệu. */
  onDone?: () => void;
};

/** Nút "Quét ngay" theo nguồn — chủ động trigger crawl tại đúng màn liên quan. */
export default function ScanNowButton({ source, label, onDone }: Props) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const run = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await scanPrices(source);
      const errored = r.sources.find((s) => s.status === "error");
      if (errored) {
        setMsg({ ok: false, text: errored.note?.slice(0, 90) || "Quét thất bại" });
      } else {
        setMsg({ ok: true, text: `Đã ghi ${r.persisted} bản ghi` });
        onDone?.();
      }
    } catch (e) {
      setMsg({ ok: false, text: String(e).slice(0, 90) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <button className="btn" onClick={run} disabled={busy}>
        {busy ? <><span className="spinner" /> Đang quét…</> : <><SyncOutlined /> {label}</>}
      </button>
      {msg && (
        <span className={`db-badge ${msg.ok ? "ok" : "err"}`} title={msg.text}>{msg.text}</span>
      )}
    </span>
  );
}
