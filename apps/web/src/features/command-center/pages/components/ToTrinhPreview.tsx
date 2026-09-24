import { CloseOutlined, PrinterOutlined } from "@ant-design/icons";
import { Button } from "antd";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { type FloorModel, fetchToTrinhHtml } from "../../../../lib/floor-suggest-client";

type Props = {
  /** Cách dùng cũ: tờ trình của 1 lần ban hành theo mô hình. */
  asOf?: string;
  model?: FloorModel;
  /** Nguồn HTML tuỳ biến (phương án nháp, bản nháp đã lưu…). Gọi 1 lần khi mở. */
  load?: () => Promise<string>;
  title?: string;
  /** Nút chèn thêm vào thanh trên (vd "Lưu bản nháp"). */
  extraActions?: ReactNode;
  onClose: () => void;
};

/** Overlay xem trước Tờ trình giá sàn (A4) trước khi xuất; nút In/Xuất PDF dùng print của trình duyệt.
 *  iframe chạy sandbox KHÔNG cho script (tờ trình là HTML tĩnh) — chỉ cho cùng origin để gọi
 *  `print()` từ trang cha và cho hộp thoại in. */
export default function ToTrinhPreview({ asOf, model, load, title, extraActions, onClose }: Props) {
  const [html, setHtml] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const frame = useRef<HTMLIFrameElement>(null);
  // Giữ hàm nạp ở ref: nơi gọi thường truyền arrow function mới mỗi lần render → không được
  // coi là "đổi nguồn" rồi nạp lại liên tục.
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    let cancelled = false;
    const loader = loadRef.current ?? (asOf ? () => fetchToTrinhHtml(asOf, model) : null);
    if (!loader) { setErr("Thiếu ngày tờ trình."); setLoading(false); return; }
    setErr(""); setLoading(true);
    loader()
      .then((h) => { if (!cancelled) setHtml(h); })
      .catch((e) => { if (!cancelled) setErr(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [asOf, model]);

  const print = () => frame.current?.contentWindow?.print();

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.55)", zIndex: 1000,
      display: "flex", flexDirection: "column", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 10, marginBottom: 10 }}>
        <b style={{ color: "#fff", fontSize: 15, flex: 1, minWidth: 200 }}>
          {title ?? `Xem trước Tờ trình giá sàn — lần ban hành ${asOf ?? ""}`}
        </b>
        {extraActions}
        <Button icon={<PrinterOutlined />} onClick={print} disabled={!html || loading}>In / Xuất PDF</Button>
        <Button icon={<CloseOutlined />} onClick={onClose}>Đóng</Button>
      </div>
      {err
        ? <div className="blt-error">{err}</div>
        : loading
          ? <div style={{ color: "#fff", padding: 24 }}>Đang dựng tờ trình…</div>
          : <iframe ref={frame} srcDoc={html} title="Tờ trình giá sàn" sandbox="allow-same-origin allow-modals"
              style={{ flex: 1, width: "100%", border: "none", borderRadius: 8, background: "#fff" }} />}
    </div>
  );
}
