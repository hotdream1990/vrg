import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

export type ListItem = { name: string; is_active: boolean };

/** Các thao tác CRUD 1 danh sách quản lý (đơn vị / khu vực) — trả về danh sách mới sau mỗi lệnh. */
export type ListApi<T extends ListItem> = {
  list: () => Promise<T[]>;
  add: (name: string) => Promise<T[]>;
  rename: (name: string, newName: string) => Promise<T[]>;
  setActive: (name: string, active: boolean) => Promise<T[]>;
  reorder: (names: string[]) => Promise<T[]>;
  remove: (name: string) => Promise<T[]>;
};

/** Cột phụ tuỳ biến (vd Khu vực, Quốc gia/Tiền) chèn giữa Tên và Trạng thái. */
export type ExtraCol<T extends ListItem> = {
  header: string;
  width?: number;
  render: (it: T, run: (fn: () => Promise<T[]>) => void) => ReactNode;
};

type Props<T extends ListItem> = {
  api: ListApi<T>;
  canEdit: boolean;
  placeholder: string;
  addLabel: string;
  countWord: string;
  nameHeader: string;
  confirmDelete: (name: string) => string;
  extraCols?: ExtraCol<T>[];
  onItemsChange?: (items: T[]) => void;
};

/** Bảng quản lý danh sách (thêm/đổi tên/ẩn-hiện/sắp xếp/xoá) dùng chung cho Đơn vị + Khu vực. */
export default function ManagedListTab<T extends ListItem>(props: Props<T>) {
  const { api, canEdit, placeholder, addLabel, countWord, nameHeader, confirmDelete } = props;
  const [items, setItems] = useState<T[]>([]);
  const [newName, setNewName] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editVal, setEditVal] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const cancelRef = useRef(false); // Esc đặt cờ này để onBlur không lưu

  const onChangeRef = useRef(props.onItemsChange);
  onChangeRef.current = props.onItemsChange;
  const apply = useCallback((next: T[]) => { setItems(next); onChangeRef.current?.(next); }, []);
  const load = useCallback(() => { api.list().then(apply).catch((e) => setErr(e.message)); }, [api, apply]);
  useEffect(() => { load(); }, [load]);

  const run = (fn: () => Promise<T[]>) => {
    setBusy(true); setErr("");
    fn().then(apply).catch((e) => setErr(e instanceof Error ? e.message : "Lỗi")).finally(() => setBusy(false));
  };

  const add = () => {
    if (!newName.trim()) return;
    setBusy(true); setErr("");
    api.add(newName.trim()).then((r) => { apply(r); setNewName(""); })
      .catch((e) => setErr(e instanceof Error ? e.message : "Lỗi")).finally(() => setBusy(false));
  };
  const saveRename = (name: string) => {
    if (!editVal.trim() || editVal.trim() === name) { setEditing(null); return; }
    setBusy(true); setErr("");
    api.rename(name, editVal.trim()).then((r) => { apply(r); setEditing(null); })
      .catch((e) => setErr(e instanceof Error ? e.message : "Lỗi")).finally(() => setBusy(false));
  };
  const move = (idx: number, dir: -1 | 1) => {
    const j = idx + dir;
    if (j < 0 || j >= items.length) return;
    const names = items.map((u) => u.name);
    [names[idx], names[j]] = [names[j], names[idx]];
    run(() => api.reorder(names));
  };

  const extraCols = props.extraCols ?? [];
  const cols = 3 + extraCols.length + (canEdit ? 1 : 0);
  return (
    <div>
      <div className="blt-toolbar">
        {canEdit && (
          <>
            <input className="blt-date-input" style={{ minWidth: 240 }} value={newName}
              placeholder={placeholder} onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") add(); }} />
            <button className="btn btn-primary" onClick={add} disabled={busy || !newName.trim()}>＋ {addLabel}</button>
          </>
        )}
        <span style={{ color: "var(--muted)", fontSize: 13 }}>{items.length} {countWord}</span>
      </div>

      {err && <div className="blt-error">{err}</div>}

      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table>
          <thead>
            <tr>
              <th style={{ width: 50 }}>#</th>
              <th>{nameHeader}</th>
              {extraCols.map((c) => <th key={c.header} style={{ width: c.width ?? 200 }}>{c.header}</th>)}
              <th style={{ width: 110 }}>Trạng thái</th>
              {canEdit && <th className="r" style={{ width: 220 }}>Thao tác</th>}
            </tr>
          </thead>
          <tbody>
            {items.map((u, i) => (
              <tr key={u.name} style={{ opacity: u.is_active ? 1 : 0.5 }}>
                <td>{i + 1}</td>
                <td>
                  {editing === u.name ? (
                    <input className="blt-cell-input" autoFocus value={editVal} style={{ minWidth: 200 }}
                      onChange={(e) => setEditVal(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") e.currentTarget.blur();
                        else if (e.key === "Escape") { cancelRef.current = true; e.currentTarget.blur(); }
                      }}
                      onBlur={() => {
                        if (cancelRef.current) { cancelRef.current = false; setEditing(null); return; }
                        saveRename(u.name);
                      }} />
                  ) : (
                    <span style={{ fontWeight: 500 }}>{u.name}</span>
                  )}
                </td>
                {extraCols.map((c) => <td key={c.header}>{c.render(u, run)}</td>)}
                <td>
                  <span className={`chip ${u.is_active ? "" : "warn"}`} style={{ fontSize: 11 }}>
                    {u.is_active ? "Đang dùng" : "Đã ẩn"}
                  </span>
                </td>
                {canEdit && (
                  <td className="r" style={{ whiteSpace: "nowrap" }}>
                    <button className="btn" onClick={() => move(i, -1)} disabled={busy || i === 0} title="Lên">↑</button>{" "}
                    <button className="btn" onClick={() => move(i, 1)} disabled={busy || i === items.length - 1} title="Xuống">↓</button>{" "}
                    <button className="btn" onClick={() => { setEditing(u.name); setEditVal(u.name); }} disabled={busy}>Đổi tên</button>{" "}
                    <button className="btn" onClick={() => run(() => api.setActive(u.name, !u.is_active))} disabled={busy}>{u.is_active ? "Ẩn" : "Hiện"}</button>{" "}
                    <button className="btn" onClick={() => { if (confirm(confirmDelete(u.name))) run(() => api.remove(u.name)); }} disabled={busy}>Xoá</button>
                  </td>
                )}
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={cols} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                Chưa có {countWord}.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
