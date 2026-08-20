import { Checkbox, Modal, Switch, message } from "antd";
import { useEffect, useMemo, useState } from "react";

import {
  type AutoSyncConfig,
  backfillAutoSync,
  fetchAutoSync,
  saveAutoSync,
} from "../../../../lib/purchase-auto-sync-client";

type Props = {
  onClose: () => void;
  /** Đã lưu (hoặc vừa lấy số) → màn Giá mủ nguyên liệu nạp lại lưới + nhãn trạng thái. */
  onSaved: (cfg: AutoSyncConfig) => void;
  readOnly?: boolean;      // quyền mức Xem: đọc được cấu hình, không lưu được
};

/** Cấu hình "Tự động lấy số từ đơn vị": công tắc tổng + chọn đơn vị nào được lấy.
 *
 *  Chuyên viên tự bật (không phải admin) vì đây là quyết định nghiệp vụ: số của đơn vị nào đủ tin
 *  để đi thẳng vào bản tin/báo cáo mà không cần Ban TTKD gõ lại. */
export default function PurchaseAutoSyncModal({ onClose, onSaved, readOnly }: Props) {
  const [cfg, setCfg] = useState<AutoSyncConfig | null>(null);
  const [on, setOn] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetchAutoSync()
      .then((c) => {
        setCfg(c);
        setOn(c.enabled);
        setPicked(c.units.filter((u) => u.auto).map((u) => u.name));
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Lỗi"));
  }, []);

  const names = useMemo(() => (cfg?.units ?? []).map((u) => u.name), [cfg]);
  const allPicked = names.length > 0 && picked.length === names.length;

  const save = async () => {
    setBusy(true); setErr("");
    try {
      const next = await saveAutoSync(on, picked);
      onSaved(next);
      message.success(on && picked.length
        ? `Đang tự động lấy số của ${picked.length} đơn vị.`
        : "Đã tắt tự động lấy số từ đơn vị.");
      onClose();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  // Bật cầu chỉ ăn từ lần đơn vị nộp SAU đó → nút này kéo nốt các ngày đơn vị đã nộp trước khi bật.
  const backfill = async () => {
    const days = cfg?.backfill_days ?? 7;
    if (!confirm(`Lấy số các đơn vị đã chọn trong ${days} ngày gần nhất?\n`
      + "Ô nào của chuyên viên đang có số khác sẽ bị ghi đè bằng số đơn vị đã nộp.")) return;
    setBusy(true); setErr("");
    try {
      const res = await backfillAutoSync(days);
      message.success(res.copied
        ? `Đã lấy ${res.copied} ô giá của ${res.companies.length} đơn vị.`
        : "Các đơn vị đã chọn chưa nộp số nào trong khoảng này.");
      if (cfg) onSaved(cfg);
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  const savedOn = cfg?.enabled && (cfg?.units ?? []).some((u) => u.auto);

  return (
    <Modal open width="min(720px, 96vw)" title="Tự động lấy số từ đơn vị" onCancel={onClose}
      okText="Lưu cấu hình" cancelText="Đóng" onOk={save}
      okButtonProps={{ loading: busy, disabled: readOnly || !cfg }} destroyOnHidden>
      <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "4px 0 12px" }}>
        <Switch checked={on} disabled={readOnly || !cfg} onChange={setOn} />
        <b>{on ? "Đang bật" : "Đang tắt"}</b>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          Đơn vị thành viên nhập giá mủ nước / mủ chén của mình → số vào thẳng lưới này, chuyên viên
          không phải gõ lại.
        </span>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <b style={{ fontSize: 13 }}>Đơn vị được lấy số tự động ({picked.length}/{names.length})</b>
        {!readOnly && (
          <button className="btn" style={{ fontSize: 12 }}
            onClick={() => setPicked(allPicked ? [] : names)}>
            {allPicked ? "Bỏ chọn tất cả" : "Chọn tất cả"}
          </button>
        )}
      </div>

      <div className="card" style={{ marginTop: 8, padding: 10, maxHeight: 300, overflow: "auto" }}>
        <Checkbox.Group value={picked} disabled={readOnly || !on}
          onChange={(v) => setPicked(v as string[])}
          style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 6 }}>
          {names.map((n) => <Checkbox key={n} value={n}>{n}</Checkbox>)}
        </Checkbox.Group>
        {cfg && names.length === 0 && (
          <div style={{ color: "var(--muted)", fontSize: 12 }}>Chưa có đơn vị nào đang hoạt động.</div>
        )}
      </div>

      <p className="form-note" style={{ fontSize: 12, marginTop: 10 }}>
        Chỉ chọn đơn vị mà số tự khai đủ tin cậy: từ lúc bật, <b>số của đơn vị là số thắng</b> — ô
        nào chuyên viên sửa tay cũng sẽ bị ghi đè ở lần đơn vị nộp tiếp theo, và đơn vị xoá giá thì
        ô bên này cũng trống theo. Muốn giữ số của mình thì bỏ đơn vị đó ra khỏi danh sách.
        Số của các đơn vị <b>không chọn</b> vẫn nhập tay như cũ.
      </p>

      {savedOn && !readOnly && (
        <button className="btn" onClick={backfill} disabled={busy} style={{ marginTop: 4 }}>
          Lấy số đã có ({cfg?.backfill_days ?? 7} ngày gần nhất)
        </button>
      )}
      {err && <div className="blt-error" style={{ marginTop: 8 }}>{err}</div>}
    </Modal>
  );
}
