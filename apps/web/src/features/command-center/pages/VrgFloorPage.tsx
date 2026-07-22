import { BankOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";

import {
  type FloorItem,
  type FloorSchedule,
  type FloorSummary,
  createFloor,
  deleteFloor,
  getFloor,
  listFloors,
  nextFloorMeta,
  updateFloor,
} from "../../../lib/floor-client";
import { todayISO } from "../../../lib/date";
import { useAuth } from "../../auth/AuthContext";
import DateInput from "../sections/DateInput";
import DataSourceNote from "../sections/DataSourceNote";
import DateRangeBar from "../sections/DateRangeBar";
import NumInput from "../sections/NumInput";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import "../../bulletin/bulletin.css";
/** Dựng items đủ chủng loại (grade thiếu → null) để form luôn hiện đủ dòng. */
const fill = (grades: string[], items: FloorItem[]): FloorItem[] => {
  const m = new Map(items.map((it) => [it.grade, it]));
  return grades.map((g) => m.get(g) ?? { grade: g, fob_usd: null, domestic_vnd: null });
};

/** Quản lý số liệu → Giá sàn Tập đoàn: biểu giá theo "lần" (số tự nhảy), nhập tay. */
export default function VrgFloorPage() {
  const { canEditCap } = useAuth();
  const canEdit = canEditCap("floor"); // mức Xem của mục này → khoá toàn bộ thao tác ghi
  const [list, setList] = useState<FloorSummary[]>([]);
  const [grades, setGrades] = useState<string[]>([]);
  const [nextLan, setNextLan] = useState(1);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [draft, setDraft] = useState<FloorSchedule | null>(null);
  const [prevItems, setPrevItems] = useState<Record<string, FloorItem>>({}); // biểu giá lần trước → cảnh báo lệch ≥10%
  const [isNew, setIsNew] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const loadList = useCallback(() => {
    listFloors(from || undefined, to || undefined).then(setList).catch((e) => setErr(e.message));
  }, [from, to]);

  useEffect(() => { loadList(); }, [loadList]);
  useEffect(() => {
    nextFloorMeta().then((m) => { setGrades(m.grades); setNextLan(m.next_lan); }).catch(() => {});
  }, [list]);

  // Biểu giá "lần" gần nhất TRƯỚC ngày `as_of` (để đối chiếu cảnh báo). Lỗi/không có → bỏ qua.
  const loadPrev = useCallback(async (as_of: string, lan?: number) => {
    try {
      const prior = list.find((s) => s.as_of < as_of && s.lan !== lan);
      if (!prior) { setPrevItems({}); return; }
      const sch = await getFloor(prior.lan);
      setPrevItems(Object.fromEntries(sch.items.map((it) => [it.grade, it])));
    } catch { setPrevItems({}); }
  }, [list]);

  const openEdition = async (lan: number) => {
    setErr("");
    try {
      const sch = await getFloor(lan);
      setDraft({ ...sch, items: fill(grades, sch.items) });
      setIsNew(false); void loadPrev(sch.as_of, sch.lan);
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
  };

  const startNew = () => {
    const as_of = todayISO();
    setDraft({ lan: nextLan, as_of, title: `Lần ${nextLan}`,
      dispatch_no: "", dispatch_summary: "", items: fill(grades, []) });
    setIsNew(true);
    setErr(""); void loadPrev(as_of);
  };

  const setCell = (idx: number, field: "fob_usd" | "domestic_vnd", v: number | null) => {
    if (!draft) return;
    const items = [...draft.items];
    items[idx] = { ...items[idx], [field]: v };
    setDraft({ ...draft, items });
  };

  const save = async () => {
    if (!draft) return;
    setBusy(true); setErr("");
    try {
      const meta = {
        title: draft.title,
        dispatch_no: draft.dispatch_no,
        dispatch_summary: draft.dispatch_summary,
      };
      const saved = isNew
        ? await createFloor(draft.as_of, draft.items, meta)
        : await updateFloor(draft.lan, draft.as_of, draft.items, meta);
      setDraft({ ...saved, items: fill(grades, saved.items) });
      setIsNew(false);
      loadList();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi lưu"); }
    finally { setBusy(false); }
  };

  const remove = async () => {
    if (!draft || isNew) return;
    if (!confirm(`Xoá biểu giá "${draft.title}" (${draft.as_of})?`)) return;
    setBusy(true);
    try { await deleteFloor(draft.lan); setDraft(null); loadList(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi xoá"); }
    finally { setBusy(false); }
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><BankOutlined style={{ marginRight: 8 }} />Giá sàn Tập đoàn</h2>
          <p>Biểu giá theo "lần" (FOB USD/T + Nội địa VNĐ/T) — nhập tay, tiêu đề tự đặt. Bản tin ngày tự lấy 2 lần mới nhất.</p>
        </div>
        {canEdit && (
          <div className="actions">
            <button className="btn btn-primary" onClick={startNew}>＋ Tạo biểu giá mới</button>
          </div>
        )}
      </div>

      <ReadOnlyNotice cap="floor" />
      <DataSourceNote page="vrg-floor" />

      <DateRangeBar from={from} to={to} onFrom={setFrom} onTo={setTo}
        info={`${list.length} biểu giá`} />

      {err && <div className="blt-error">{err}</div>}

      {/* Danh sách các lần */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head"><div><h3>Các lần đã có</h3></div></div>
        {list.length === 0 ? (
          <div className="scan-empty">{canEdit ? 'Chưa có biểu giá nào — bấm "Tạo biểu giá mới".' : "Chưa có biểu giá nào."}</div>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {list.map((s) => (
              <button key={s.lan} className={`btn${draft?.lan === s.lan && !isNew ? " btn-primary" : ""}`}
                onClick={() => openEdition(s.lan)}>
                {s.title}{s.dispatch_no ? ` · CV ${s.dispatch_no}` : ""} · {s.as_of}{" "}
                <span style={{ opacity: 0.7 }}>({s.grades} chủng loại)</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Editor 1 biểu giá */}
      {draft && (
        <div className="card blt-section blt-editable">
          <div className="blt-section-header">
            <h3>{isNew ? "Biểu giá mới" : "Sửa biểu giá"}</h3>
            <div className="blt-section-meta" style={{ alignItems: "center" }}>
              <label className="blt-date-label">Tiêu đề:
                <input type="text" className="blt-date-input" style={{ width: 130 }}
                  value={draft.title} readOnly={!canEdit} placeholder="Lần 15"
                  onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
              </label>
              <label className="blt-date-label">Số công văn:
                <input type="text" className="blt-date-input" style={{ width: 160 }}
                  value={draft.dispatch_no ?? ""} readOnly={!canEdit} placeholder="VD: 123/CSVN-TT"
                  onChange={(e) => setDraft({ ...draft, dispatch_no: e.target.value })} />
              </label>
              <label className="blt-date-label">Ngày áp dụng:
                <DateInput value={draft.as_of} readOnly={!canEdit}
                  onChange={(v) => setDraft({ ...draft, as_of: v })} />
              </label>
              {canEdit && (
                <>
                  <button className="btn btn-primary" onClick={save} disabled={busy}>
                    {busy ? <span className="spinner" /> : null} Lưu biểu giá
                  </button>
                  {!isNew && <button className="btn" onClick={remove} disabled={busy}>Xoá</button>}
                </>
              )}
            </div>
          </div>
          <label className="blt-date-label" style={{ display: "block", marginBottom: 14 }}>Trích yếu nội dung công văn
            <textarea className="blt-date-input" style={{ width: "100%", minHeight: 54, resize: "vertical", marginTop: 4 }}
              value={draft.dispatch_summary ?? ""} readOnly={!canEdit}
              placeholder="Trích yếu nội dung công văn…"
              onChange={(e) => setDraft({ ...draft, dispatch_summary: e.target.value })} />
          </label>
          <table>
            <thead>
              <tr>
                <th>Chủng loại</th>
                <th className="r">Giá XK FOB/FCA (USD/T)</th>
                <th className="r">Giá nội địa (VNĐ/T)</th>
              </tr>
            </thead>
            <tbody>
              {draft.items.map((it, i) => (
                <tr key={it.grade}>
                  <td>{it.grade}</td>
                  <td className="r">
                    <NumInput value={it.fob_usd} readOnly={!canEdit} prevValue={prevItems[it.grade]?.fob_usd}
                      onChange={(v) => setCell(i, "fob_usd", v)} />
                  </td>
                  <td className="r">
                    <NumInput value={it.domestic_vnd} readOnly={!canEdit} prevValue={prevItems[it.grade]?.domestic_vnd}
                      onChange={(v) => setCell(i, "domestic_vnd", v)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
