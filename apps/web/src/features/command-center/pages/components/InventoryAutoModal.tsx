import { Modal, Switch, message } from "antd";
import { useEffect, useState } from "react";

import {
  type InventoryAutoConfig,
  type InventoryAutoPreview,
  applyInventoryAuto,
  fetchInventoryAuto,
  previewInventoryAuto,
  recomputeInventoryAuto,
  saveInventoryAuto,
} from "../../../../lib/inventory-client";

type Props = {
  onClose: () => void;
  /** Đã lưu / vừa đồng bộ → màn Tồn kho nạp lại chuỗi tuần + nhãn trạng thái. */
  onSaved: (cfg: InventoryAutoConfig) => void;
  readOnly?: boolean;      // quyền mức Xem: đọc được cấu hình, không bấm được nút ghi
};

const fmt = (n: number | null) =>
  (n == null ? "—" : n.toLocaleString("vi-VN", { maximumFractionDigits: 1 }));

/** Cấu hình "Tự tính tồn kho từ số liệu đơn vị thành viên".
 *
 *  Chuyên viên tự bật (không phải admin): quyết định số nào vào chuỗi tuần của Tập đoàn là việc
 *  của người phụ trách số liệu tồn kho. Nút đồng bộ 1 tuần luôn dùng được, kể cả khi đang tắt. */
export default function InventoryAutoModal({ onClose, onSaved, readOnly }: Props) {
  const [cfg, setCfg] = useState<InventoryAutoConfig | null>(null);
  const [on, setOn] = useState(false);
  const [pre, setPre] = useState<InventoryAutoPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetchInventoryAuto()
      .then((c) => {
        setCfg(c); setOn(c.enabled);
        return previewInventoryAuto(c.last_anchor).then(setPre);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Lỗi"));
  }, []);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setErr("");
    try { await fn(); } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  const save = () => run(async () => {
    const next = await saveInventoryAuto(on);
    setCfg(next); onSaved(next);
    message.success(on
      ? "Đã bật: mỗi lần đơn vị nộp/sửa biểu Tồn kho, tuần tương ứng được tính lại."
      : "Đã tắt tự tính. Nút đồng bộ từng tuần vẫn dùng được.");
    onClose();
  });

  // Đồng bộ NGAY tuần chốt gần nhất — thao tác cố ý nên ghi đè cả số nhập tay.
  const applyWeek = () => run(async () => {
    if (!cfg || !pre) return;
    if (!confirm(`Ghi số tự tính cho tuần ${cfg.last_anchor}?\n`
      + `Tồn kho ${fmt(pre.ton_kho)} tấn · Đã có HĐ ${fmt(pre.ton_kho_hd)} tấn `
      + `(${pre.units_counted}/${pre.units_expected} đơn vị có số).\n`
      + "Số đang có của tuần này (kể cả nhập tay) sẽ bị thay.")) return;
    const res = await applyInventoryAuto(cfg.last_anchor);
    onSaved(cfg);
    message.success(`Đã ghi tuần ${cfg.last_anchor}: ${fmt(res.week.ton_kho)} tấn.`);
  });

  // Bật công tắc chỉ ăn từ lần đơn vị nộp SAU đó → nút này lấp các tuần đã có số đơn vị.
  const recompute = () => run(async () => {
    const weeks = cfg?.recompute_weeks ?? 8;
    if (!confirm(`Tính lại ${weeks} tuần gần nhất từ số liệu đơn vị?\n`
      + "Các tuần chuyên viên đã nhập tay được GIỮ NGUYÊN.")) return;
    const res = await recomputeInventoryAuto(weeks);
    if (cfg) onSaved(cfg);
    message.success(res.written.length
      ? `Đã ghi ${res.written.length} tuần; giữ nguyên ${res.kept_manual.length} tuần nhập tay.`
      : `Không tuần nào được ghi (giữ nguyên ${res.kept_manual.length} tuần nhập tay).`);
  });

  return (
    <Modal open width="min(680px, 96vw)" title="Tự tính tồn kho từ số liệu đơn vị" onCancel={onClose}
      okText="Lưu cấu hình" cancelText="Đóng" onOk={save}
      okButtonProps={{ loading: busy, disabled: readOnly || !cfg }} destroyOnHidden>
      <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "4px 0 12px" }}>
        <Switch checked={on} disabled={readOnly || !cfg} onChange={setOn} />
        <b>{on ? "Đang bật" : "Đang tắt"}</b>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          Đơn vị thành viên nộp/sửa biểu Tồn kho → tuần tương ứng của Tập đoàn được cộng lại ngay,
          chuyên viên không phải gõ tay.
        </span>
      </div>

      <div className="card" style={{ padding: 12 }}>
        <b style={{ fontSize: 13 }}>Tuần chốt gần nhất — {cfg?.last_anchor ?? "…"}</b>
        {pre ? (
          <div style={{ marginTop: 8, display: "grid", gap: 4, fontSize: 13 }}>
            <div>Tồn kho: <b>{fmt(pre.ton_kho)}</b> tấn · Đã có HĐ: <b>{fmt(pre.ton_kho_hd)}</b> tấn</div>
            <div style={{ color: "var(--muted)", fontSize: 12 }}>
              {pre.units_counted}/{pre.units_expected} đơn vị có số
              {pre.missing.length > 0 && ` — chưa có số: ${pre.missing.slice(0, 4).join(", ")}`}
              {pre.missing.length > 4 && ` …và ${pre.missing.length - 4} đơn vị khác`}
            </div>
          </div>
        ) : <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 6 }}>Đang tính…</div>}
        {!readOnly && (
          <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
            <button className="btn" onClick={applyWeek} disabled={busy || !pre}>
              Đồng bộ tuần {cfg?.last_anchor ?? ""}
            </button>
            <button className="btn" onClick={recompute} disabled={busy || !cfg}>
              Tính lại {cfg?.recompute_weeks ?? 8} tuần gần nhất
            </button>
          </div>
        )}
      </div>

      <p className="form-note" style={{ fontSize: 12, marginTop: 10 }}>
        Chốt <b>{cfg?.weekday_label ?? "thứ Sáu hằng tuần"}</b> — đúng chu kỳ đang nhập tay. Đơn vị
        <b> khai tồn ngày chốt</b> thì lấy số ngày đó; đơn vị tick <b>“không phát sinh tồn kho để
        khai”</b> thì giữ nguyên số của lần khai gần nhất; đơn vị <b>chưa khai gì</b> thì không có
        số — không đắp số ngày khác vào, mà ghi rõ ở ghi chú của tuần.
        Tồn kho = khối <b>“Đã nhập kho”</b>; Đã có HĐ = phần đã ký chưa giao, <b>cắt trần</b> theo
        tồn kho của chính đơn vị đó. Tuần chuyên viên đã nhập tay <b>không bị đè</b> — muốn thay thì
        bấm nút đồng bộ của đúng tuần đó.
      </p>

      {err && <div className="blt-error" style={{ marginTop: 8 }}>{err}</div>}
    </Modal>
  );
}
