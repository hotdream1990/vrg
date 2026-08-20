import { InboxOutlined, SyncOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  type InventoryAutoConfig,
  type InventoryWeek,
  applyInventoryAuto,
  deleteInventory,
  fetchInventory,
  fetchInventoryAuto,
  previewInventoryAuto,
  upsertInventory,
} from "../../../lib/inventory-client";
import { isBigChange } from "../../../lib/change-warning";
import { useEditorWindow } from "../../../lib/edit-window";
import { useAuth } from "../../auth/AuthContext";
import ChangeWarn from "../sections/ChangeWarn";
import DateInput from "../sections/DateInput";
import DataSourceNote from "../sections/DataSourceNote";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import InventoryAutoModal from "./components/InventoryAutoModal";
import "../../bulletin/bulletin.css";

// Số tự tính cộng từ hàng chục đơn vị nên lẻ tới hàng kg — hiển thị 1 số lẻ cho đỡ rối,
// DB vẫn giữ nguyên số đầy đủ (không làm tròn dữ liệu).
const fmt = (n: number | null) =>
  (n == null ? "—" : n.toLocaleString("vi-VN", { maximumFractionDigits: 1 }));
const EMPTY = { as_of: "", ton_kho: "", ton_kho_hd: "", note: "" };

/** Quản lý số liệu → Tồn kho Tập đoàn: chuỗi tuần (tồn kho + tồn kho đã có hợp đồng), nhập/sửa/xoá. */
export default function InventoryPage() {
  const { canEditCap } = useAuth();
  const canEdit = canEditCap("inventory"); // mức Xem của mục này → khoá toàn bộ thao tác ghi
  const ew = useEditorWindow(); // cửa sổ sửa: tuần cũ hơn N ngày → chỉ xem (admin miễn)
  const [weeks, setWeeks] = useState<InventoryWeek[]>([]);
  const [form, setForm] = useState({ ...EMPTY });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [auto, setAuto] = useState<InventoryAutoConfig | null>(null);
  const [autoOpen, setAutoOpen] = useState(false);

  const load = useCallback(() => {
    fetchInventory().then(setWeeks).catch((e) => setErr(e.message));
    fetchInventoryAuto().then(setAuto).catch(() => setAuto(null));
  }, []);
  useEffect(() => { load(); }, [load]);

  const num = (s: string) => (s.trim() === "" ? null : Number(s.replace(/[.,\s]/g, "")));

  // Tuần gần nhất TRƯỚC tuần đang nhập → đối chiếu cảnh báo lệch ≥10%.
  const prevWeek = useMemo(() => {
    if (!form.as_of) return null;
    return weeks.filter((w) => w.as_of < form.as_of)
      .sort((a, b) => b.as_of.localeCompare(a.as_of))[0] ?? null;
  }, [weeks, form.as_of]);
  const warnTon = isBigChange(num(form.ton_kho), prevWeek?.ton_kho);
  const warnTonHd = isBigChange(num(form.ton_kho_hd), prevWeek?.ton_kho_hd);

  const save = async () => {
    if (!form.as_of) { setErr("Chọn ngày tuần"); return; }
    if (!ew.isEditable(form.as_of)) {
      setErr(`Tuần ${form.as_of} đã ngoài cửa sổ sửa — chỉ nhập được ${ew.days ?? 7} ngày gần nhất.`);
      return;
    }
    setBusy(true); setErr("");
    try {
      await upsertInventory({ as_of: form.as_of, ton_kho: num(form.ton_kho), ton_kho_hd: num(form.ton_kho_hd), note: form.note || null });
      setForm({ ...EMPTY }); load();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  const edit = (w: InventoryWeek) => setForm({
    as_of: w.as_of, ton_kho: w.ton_kho?.toString() ?? "",
    ton_kho_hd: w.ton_kho_hd?.toString() ?? "", note: w.note ?? "",
  });

  // Đồng bộ 1 tuần theo số đơn vị — dùng được cả khi công tắc tự tính đang TẮT (thao tác cố ý
  // của chuyên viên nên được ghi đè số đang có, kể cả số nhập tay).
  const syncWeek = async (as_of: string) => {
    setBusy(true); setErr("");
    try {
      const pre = await previewInventoryAuto(as_of);
      if (!pre.units_counted) {
        setErr(`Chưa đơn vị nào có số tồn kho cho tuần ${as_of}.`);
        return;
      }
      if (!confirm(`Đồng bộ tuần ${as_of} theo số liệu đơn vị?\n`
        + `Tồn kho ${fmt(pre.ton_kho)} tấn · Đã có HĐ ${fmt(pre.ton_kho_hd)} tấn `
        + `(${pre.units_counted}/${pre.units_expected} đơn vị có số).\n`
        + "Số đang có của tuần này sẽ bị thay.")) return;
      await applyInventoryAuto(as_of);
      load();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  const remove = async (as_of: string) => {
    if (!confirm(`Xoá số liệu tồn kho tuần ${as_of}?`)) return;
    setBusy(true); setErr("");
    try { await deleteInventory(as_of); load(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><InboxOutlined style={{ marginRight: 8 }} />Tồn kho Tập đoàn</h2>
          <p>Chuỗi tồn kho thành phẩm theo tuần (từ báo cáo tuần chị Hạnh): <b>Tồn kho</b> và <b>Tồn kho đã có hợp đồng</b> (đơn vị: tấn). Nhập/sửa thủ công, nạp từ file PDF, hoặc <b>tự tính từ biểu Tồn kho của các đơn vị thành viên</b>.</p>
        </div>
      </div>

      <ReadOnlyNotice cap="inventory" />
      <DataSourceNote page="inventory" />

      {canEdit && (
        <div className="card" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
          <label className="blt-date-label">Ngày tuần
            <DateInput value={form.as_of} onChange={(v) => setForm({ ...form, as_of: v })} />
          </label>
          <label className="blt-date-label">Tồn kho (tấn)
            <input className={`blt-date-input${warnTon ? " num-warn" : ""}`} inputMode="numeric" value={form.ton_kho}
              placeholder="vd: 24767" onChange={(e) => setForm({ ...form, ton_kho: e.target.value })} />
            <ChangeWarn value={num(form.ton_kho)} prev={prevWeek?.ton_kho} />
          </label>
          <label className="blt-date-label">Tồn kho đã có HĐ (tấn)
            <input className={`blt-date-input${warnTonHd ? " num-warn" : ""}`} inputMode="numeric" value={form.ton_kho_hd}
              placeholder="vd: 23339" onChange={(e) => setForm({ ...form, ton_kho_hd: e.target.value })} />
            <ChangeWarn value={num(form.ton_kho_hd)} prev={prevWeek?.ton_kho_hd} />
          </label>
          <label className="blt-date-label" style={{ flex: 1, minWidth: 160 }}>Ghi chú
            <input className="blt-date-input" value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </label>
          <button className="btn btn-primary" onClick={save}
            disabled={busy || !form.as_of || !ew.isEditable(form.as_of)}>
            {weeks.some((w) => w.as_of === form.as_of) ? "Cập nhật tuần" : "＋ Thêm tuần"}
          </button>
          {form.as_of && (
            <button className="btn" onClick={() => syncWeek(form.as_of)} disabled={busy}
              title="Lấy số tự tính từ số liệu đơn vị thành viên cho ngày này">Đồng bộ ngày này</button>
          )}
          {form.as_of && <button className="btn" onClick={() => setForm({ ...EMPTY })} disabled={busy}>Hủy</button>}
        </div>
      )}

      {err && <div className="blt-error">{err}</div>}

      <div className="blt-toolbar" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ color: "var(--muted)", fontSize: 13 }}>{weeks.length} tuần</span>
        {auto && (
          <span className="chip" style={{ fontSize: 11 }}>
            Tự tính từ đơn vị: {auto.enabled ? "đang bật" : "đang tắt"}
          </span>
        )}
        {canEdit && (
          <button className="btn" style={{ marginLeft: "auto" }} onClick={() => setAutoOpen(true)}>
            <SyncOutlined style={{ marginRight: 6 }} />Tự tính từ số liệu đơn vị
          </button>
        )}
      </div>

      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table>
          <thead><tr>
            <th>Ngày tuần</th><th className="r">Tồn kho (tấn)</th><th className="r">Đã có HĐ (tấn)</th>
            <th>Nguồn</th>{canEdit && <th className="r" style={{ width: 140 }}>Thao tác</th>}
          </tr></thead>
          <tbody>
            {weeks.map((w) => {
              const ed = ew.isEditable(w.as_of);
              return (
              <tr key={w.as_of} style={{ background: form.as_of === w.as_of ? "var(--card-2, #eef6f0)" : undefined }}>
                <td style={{ fontWeight: 500 }}>
                  {w.as_of}
                  {canEdit && !ed && <span style={{ color: "var(--muted)", fontSize: 11, marginLeft: 6 }}>(chỉ xem)</span>}
                </td>
                <td className="r">{fmt(w.ton_kho)}</td>
                <td className="r">{fmt(w.ton_kho_hd)}</td>
                <td>
                  <span className="chip" style={{ fontSize: 11 }} title={w.note ?? undefined}>
                    {w.source === "hanh_weekly" ? "PDF tuần" : w.source === "auto" ? "Tự tính" : "Nhập tay"}
                  </span>
                </td>
                {canEdit && (
                  <td className="r" style={{ whiteSpace: "nowrap" }}>
                    {/* Đồng bộ chạy được cả ngoài cửa sổ sửa: số do máy cộng từ chuỗi ngày của
                        đơn vị, không phải người gõ tay — và luôn nhập tay lại được. */}
                    <button className="btn" title="Lấy số tự tính từ đơn vị thành viên cho tuần này"
                      onClick={() => syncWeek(w.as_of)} disabled={busy}>Đồng bộ</button>{" "}
                    {ed ? (
                      <>
                        <button className="btn" onClick={() => edit(w)} disabled={busy}>Sửa</button>{" "}
                        <button className="btn" onClick={() => remove(w.as_of)} disabled={busy}>Xoá</button>
                      </>
                    ) : <span style={{ color: "var(--muted)" }}>—</span>}
                  </td>
                )}
              </tr>
              );
            })}
            {weeks.length === 0 && (
              <tr><td colSpan={canEdit ? 5 : 4} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>Chưa có dữ liệu tồn kho.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {autoOpen && (
        <InventoryAutoModal readOnly={!canEdit} onClose={() => setAutoOpen(false)}
          onSaved={(cfg) => { setAuto(cfg); load(); }} />
      )}
    </div>
  );
}
