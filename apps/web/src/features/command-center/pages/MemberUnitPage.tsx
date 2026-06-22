import { TeamOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";

import {
  type MemberUnit,
  addUnit,
  deleteUnit,
  listUnits,
  reorderUnits,
  updateUnit,
} from "../../../lib/member-unit-client";
import { useAuth } from "../../auth/AuthContext";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import "../../bulletin/bulletin.css";

/** Quản lý số liệu → Đơn vị thành viên: danh sách công ty cho Giá mủ nguyên liệu (động). */
export default function MemberUnitPage() {
  const { canEdit } = useAuth();
  const [units, setUnits] = useState<MemberUnit[]>([]);
  const [newName, setNewName] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editVal, setEditVal] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    listUnits().then(setUnits).catch((e) => setErr(e.message));
  }, []);
  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<MemberUnit[]>) => {
    setBusy(true); setErr("");
    try { setUnits(await fn()); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  const add = () => {
    if (!newName.trim()) return;
    run(() => addUnit(newName.trim())).then(() => setNewName(""));
  };
  const saveRename = (name: string) => {
    if (!editVal.trim() || editVal.trim() === name) { setEditing(null); return; }
    run(() => updateUnit(name, { new_name: editVal.trim() })).then(() => setEditing(null));
  };
  const toggle = (u: MemberUnit) => run(() => updateUnit(u.name, { is_active: !u.is_active }));
  const remove = (name: string) => {
    if (!confirm(`Xoá đơn vị "${name}" khỏi danh sách? (Giá đã nhập vẫn giữ trong kho)`)) return;
    run(() => deleteUnit(name));
  };
  const move = (idx: number, dir: -1 | 1) => {
    const j = idx + dir;
    if (j < 0 || j >= units.length) return;
    const names = units.map((u) => u.name);
    [names[idx], names[j]] = [names[j], names[idx]];
    run(() => reorderUnits(names));
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><TeamOutlined style={{ marginRight: 8 }} />Đơn vị thành viên</h2>
          <p>Danh sách công ty thành viên VRG dùng cho "Giá mủ nguyên liệu" — thêm, đổi tên, ẩn/hiện, sắp xếp. Đổi tên sẽ giữ nguyên lịch sử giá đã nhập.</p>
        </div>
      </div>

      <ReadOnlyNotice />

      <div className="blt-toolbar">
        {canEdit && (
          <>
            <input className="blt-date-input" style={{ minWidth: 240 }} value={newName}
              placeholder="Tên đơn vị mới (vd: Bình Long)" onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") add(); }} />
            <button className="btn btn-primary" onClick={add} disabled={busy || !newName.trim()}>＋ Thêm đơn vị</button>
          </>
        )}
        <span style={{ color: "var(--muted)", fontSize: 13 }}>{units.length} đơn vị</span>
      </div>

      {err && <div className="blt-error">{err}</div>}

      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table>
          <thead>
            <tr>
              <th style={{ width: 50 }}>#</th>
              <th>Tên đơn vị</th>
              <th style={{ width: 110 }}>Trạng thái</th>
              {canEdit && <th className="r" style={{ width: 220 }}>Thao tác</th>}
            </tr>
          </thead>
          <tbody>
            {units.map((u, i) => (
              <tr key={u.name} style={{ opacity: u.is_active ? 1 : 0.5 }}>
                <td>{i + 1}</td>
                <td>
                  {editing === u.name ? (
                    <input className="blt-cell-input" autoFocus value={editVal}
                      style={{ minWidth: 200 }}
                      onChange={(e) => setEditVal(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") saveRename(u.name);
                        if (e.key === "Escape") setEditing(null);
                      }}
                      onBlur={() => saveRename(u.name)} />
                  ) : (
                    <span style={{ fontWeight: 500 }}>{u.name}</span>
                  )}
                </td>
                <td>
                  <span className={`chip ${u.is_active ? "" : "warn"}`} style={{ fontSize: 11 }}>
                    {u.is_active ? "Đang dùng" : "Đã ẩn"}
                  </span>
                </td>
                {canEdit && (
                  <td className="r" style={{ whiteSpace: "nowrap" }}>
                    <button className="btn" onClick={() => move(i, -1)} disabled={busy || i === 0} title="Lên">↑</button>{" "}
                    <button className="btn" onClick={() => move(i, 1)} disabled={busy || i === units.length - 1} title="Xuống">↓</button>{" "}
                    <button className="btn" onClick={() => { setEditing(u.name); setEditVal(u.name); }} disabled={busy}>Đổi tên</button>{" "}
                    <button className="btn" onClick={() => toggle(u)} disabled={busy}>{u.is_active ? "Ẩn" : "Hiện"}</button>{" "}
                    <button className="btn" onClick={() => remove(u.name)} disabled={busy}>Xoá</button>
                  </td>
                )}
              </tr>
            ))}
            {units.length === 0 && (
              <tr><td colSpan={canEdit ? 4 : 3} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                Chưa có đơn vị.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
