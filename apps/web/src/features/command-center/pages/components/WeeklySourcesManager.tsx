/* Hộp thoại "Quản lý nguồn tham khảo" (chỉ người có quyền Sửa báo cáo tuần): danh sách + thêm/sửa,
   bật/tắt nhanh, xoá, khôi phục danh mục mặc định. Lỗi kiểm tra của máy chủ hiện nguyên văn. */

import { DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { Modal, Switch } from "antd";
import { useState } from "react";

import {
  type WeeklySource,
  type WeeklySourceInput,
  type WeeklySourceMeta,
  createWeeklySource,
  deleteWeeklySource,
  optionLabel,
  resetWeeklySources,
  toSourceInput,
  updateWeeklySource,
} from "../../../../lib/weekly-sources-client";
import WeeklySourceForm, { EMPTY_SOURCE } from "./WeeklySourceForm";

type Props = {
  sources: WeeklySource[];
  meta: WeeklySourceMeta;
  onClose: () => void;
  /** Có thay đổi → trang nạp lại danh mục nguồn. */
  onChanged: () => Promise<void> | void;
};

type Editing = { id: number | null; initial: WeeklySourceInput } | null;

export default function WeeklySourcesManager({ sources, meta, onClose, onChanged }: Props) {
  const [editing, setEditing] = useState<Editing>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setErr("");
    try { await fn(); await onChanged(); return true; }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); return false; }
    finally { setBusy(false); }
  };

  const submit = async (v: WeeklySourceInput) => {
    const id = editing?.id ?? null;
    const ok = await run(() => (id === null ? createWeeklySource(v) : updateWeeklySource(id, v)));
    if (ok) setEditing(null);
  };
  const toggle = (s: WeeklySource, enabled: boolean) =>
    run(() => updateWeeklySource(s.id, { ...toSourceInput(s), enabled }));
  const remove = (s: WeeklySource) => {
    if (confirm(`Xoá nguồn "${s.name}"?`)) run(() => deleteWeeklySource(s.id));
  };
  const reset = () => {
    if (confirm("Khôi phục danh mục nguồn MẶC ĐỊNH? Các nguồn đã thêm/sửa sẽ bị thay bằng danh mục gốc.")) {
      run(() => resetWeeklySources());
    }
  };

  const sorted = [...sources].sort((a, b) => a.category.localeCompare(b.category) || a.sort_order - b.sort_order);

  return (
    <Modal open width={960} title="Quản lý nguồn tham khảo — Báo cáo tuần" onCancel={onClose} footer={null}
      destroyOnHidden>
      {err && <div className="blt-error">{err}</div>}
      {editing ? (
        <WeeklySourceForm key={editing.id ?? "new"} initial={editing.initial} meta={meta} busy={busy}
          onSubmit={submit} onCancel={() => { setEditing(null); setErr(""); }} />
      ) : (
        <>
          <div className="wk-form-actions wk-form-actions-top">
            <button className="btn" onClick={reset} disabled={busy}><ReloadOutlined /> Khôi phục mặc định</button>
            <button className="btn btn-primary" disabled={busy}
              onClick={() => setEditing({ id: null, initial: { ...EMPTY_SOURCE, category: meta.categories[0]?.key ?? "news" } })}>
              <PlusOutlined /> Thêm nguồn
            </button>
          </div>
          <div className="wk-scroll">
            <table className="wk-table wk-table-sm">
              <thead>
                <tr><th>Bật</th><th>Loại</th><th>Tên nguồn</th><th>Cách lấy</th><th>Mục dùng</th><th /></tr>
              </thead>
              <tbody>
                {sorted.length === 0 && <tr><td colSpan={6} className="c wk-muted">Chưa có nguồn nào.</td></tr>}
                {sorted.map((s) => (
                  <tr key={s.id} className={s.enabled ? "" : "wk-row-off"}>
                    <td className="c"><Switch size="small" checked={s.enabled} disabled={busy}
                      onChange={(on) => toggle(s, on)} /></td>
                    <td>{optionLabel(meta.categories, s.category)}</td>
                    <td>
                      <div className="wk-strong">{s.name}</div>
                      {s.url && <div className="wk-muted wk-ellipsis">{s.url}</div>}
                    </td>
                    <td>{optionLabel(meta.modes, s.mode)}{s.feed_symbol ? ` (${s.feed_symbol})` : ""}</td>
                    <td>{(s.sections ?? []).join(", ")}</td>
                    <td className="c wk-nowrap">
                      <button className="btn btn-sm" disabled={busy} title="Sửa"
                        onClick={() => setEditing({ id: s.id, initial: toSourceInput(s) })}><EditOutlined /></button>{" "}
                      <button className="btn btn-sm" disabled={busy} title="Xoá" onClick={() => remove(s)}>
                        <DeleteOutlined />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Modal>
  );
}
