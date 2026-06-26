import { CloseOutlined, PrinterOutlined } from "@ant-design/icons";
import { useEffect, useRef, useState } from "react";

import { type FloorModel, fetchToTrinhHtml } from "../../../../lib/floor-suggest-client";

const btn: React.CSSProperties = {
  display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer",
  border: "1px solid #d0d7d2", borderRadius: 8, padding: "7px 14px", fontWeight: 600, background: "#fff",
};

/** Overlay xem trước Tờ trình giá sàn (A4) trước khi xuất; nút In/Xuất PDF dùng print của trình duyệt. */
export default function ToTrinhPreview(
  { asOf, model, onClose }: { asOf: string; model: FloorModel; onClose: () => void },
) {
  const [html, setHtml] = useState("");
  const [err, setErr] = useState("");
  const frame = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    setErr("");
    fetchToTrinhHtml(asOf, model).then(setHtml).catch((e) => setErr(e.message));
  }, [asOf, model]);

  const print = () => frame.current?.contentWindow?.print();

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.55)", zIndex: 1000,
      display: "flex", flexDirection: "column", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <b style={{ color: "#fff", fontSize: 15, flex: 1 }}>Xem trước Tờ trình giá sàn — lần ban hành {asOf}</b>
        <button style={btn} onClick={print}><PrinterOutlined /> In / Xuất PDF</button>
        <button style={btn} onClick={onClose}><CloseOutlined /> Đóng</button>
      </div>
      {err
        ? <div className="blt-error">{err}</div>
        : <iframe ref={frame} srcDoc={html} title="Tờ trình giá sàn"
            style={{ flex: 1, width: "100%", border: "none", borderRadius: 8, background: "#fff" }} />}
    </div>
  );
}
