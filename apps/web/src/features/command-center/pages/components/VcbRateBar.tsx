/* Header phiếu — tỷ giá Vietcombank (Mua TM / Mua CK / Bán), có nút lấy realtime từ VCB. */

import { CloudDownloadOutlined } from "@ant-design/icons";
import { useState } from "react";

import { type VcbRate, fetchVcbRate } from "../../../../lib/market-quote-client";
import NumInput from "../../sections/NumInput";

type Props = { fx: VcbRate; date: string; readOnly?: boolean; onChange: (fx: VcbRate) => void; prevFx?: VcbRate | null };

const FIELDS: { key: keyof VcbRate; label: string }[] = [
  { key: "mua_tm", label: "Mua TM" },
  { key: "mua_ck", label: "Mua CK" },
  { key: "ban", label: "Bán" },
];

export default function VcbRateBar({ fx, date, readOnly, onChange, prevFx }: Props) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const grab = async () => {
    setBusy(true); setMsg("");
    try {
      const r = await fetchVcbRate(date || undefined);
      onChange({ mua_tm: r.mua_tm, mua_ck: r.mua_ck, ban: r.ban });
      setMsg(`Đã lấy VCB ${r.date}`);
    } catch {
      setMsg("Không lấy được — nhập tay");
    } finally { setBusy(false); }
  };

  return (
    <div className="card" style={{ display: "flex", gap: 18, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 16 }}>
      <div style={{ fontWeight: 700 }}>Tỷ giá VCB (USD)</div>
      {FIELDS.map((f) => (
        <label key={f.key} className="blt-date-label">{f.label}
          <NumInput value={fx[f.key]} readOnly={readOnly} prevValue={prevFx?.[f.key]}
            onChange={(v) => onChange({ ...fx, [f.key]: v })} />
        </label>
      ))}
      {!readOnly && (
        <button className="btn" onClick={grab} disabled={busy}>
          {busy ? <span className="spinner" /> : <CloudDownloadOutlined />} Lấy tỷ giá VCB
        </button>
      )}
      {msg && <span style={{ color: "var(--muted)", fontSize: 12 }}>{msg}</span>}
      <span style={{ color: "var(--muted)", fontSize: 12 }}>Nguồn: Vietcombank · VNĐ/USD</span>
    </div>
  );
}
