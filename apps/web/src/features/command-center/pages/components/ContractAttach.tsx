import { DeleteOutlined, PaperClipOutlined, UploadOutlined } from "@ant-design/icons";
import { useRef, useState } from "react";

import {
  type ContractDoc,
  contractFileUrl,
  uploadContractFile,
} from "../../../../lib/sales-contract-client";

type Props = {
  label: string;
  docs: ContractDoc[];
  readOnly?: boolean;
  onChange: (docs: ContractDoc[]) => void;
};

/** Ô đính kèm NHIỀU file (hợp đồng scan · chứng từ/hoá đơn thanh toán). */
export default function ContractAttach({ label, docs, readOnly, onChange }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const pick = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true); setErr("");
    try {
      const added: ContractDoc[] = [];
      for (const f of Array.from(files)) {
        const saved = await uploadContractFile(f);
        added.push({ file: saved.file, filename: saved.filename });
      }
      onChange([...docs, ...added]);
    } catch (e) { setErr(e instanceof Error ? e.message : "Tải file thất bại."); }
    finally { setBusy(false); if (input.current) input.current.value = ""; }
  };

  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>{label}</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        {docs.map((d) => (
          <span key={d.file} className="chip" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
            <PaperClipOutlined />
            <a href={contractFileUrl(d)} target="_blank" rel="noreferrer">{d.filename ?? d.file}</a>
            {!readOnly && (
              <button className="btn" style={{ padding: "0 4px" }} title="Bỏ file"
                onClick={() => onChange(docs.filter((x) => x.file !== d.file))}>
                <DeleteOutlined />
              </button>
            )}
          </span>
        ))}
        {!readOnly && (
          <>
            <input ref={input} type="file" multiple hidden onChange={(e) => pick(e.target.files)} />
            <button className="btn" disabled={busy} onClick={() => input.current?.click()}>
              <UploadOutlined /> {busy ? "Đang tải…" : "Chọn file"}
            </button>
          </>
        )}
        {docs.length === 0 && readOnly && <span style={{ color: "var(--muted)" }}>—</span>}
      </div>
      {err && <div className="blt-error" style={{ marginTop: 6 }}>{err}</div>}
    </div>
  );
}
