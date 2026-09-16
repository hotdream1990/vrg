import { ApartmentOutlined, EditOutlined, FormOutlined, PlusOutlined, SendOutlined } from "@ant-design/icons";
import { Alert, Select, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  type DemandEntry,
  type DemandTimeline,
  fetchDemandTimeline,
  fetchMyDemandTimeline,
  saveDemand,
  saveMyDemand,
} from "../../../lib/market-demand-client";
import { dmy, todayISO } from "../../../lib/date";
import { DIRECT_SAVED_IN_REQUEST_MODE, useEditRequest } from "../../../lib/use-edit-request";
import { useAuth } from "../../auth/AuthContext";
import DateInput from "../sections/DateInput";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import "../../bulletin/bulletin.css";

const daysBetween = (later: string, earlier: string) =>
  Math.round((new Date(later + "T00:00:00").getTime() - new Date(earlier + "T00:00:00").getTime()) / 86400000);
const RANGES = [30, 60, 90, 180, 365];

const taStyle: React.CSSProperties = {
  width: "100%", resize: "vertical", padding: "9px 11px", borderRadius: 8,
  border: "1px solid #d9e1dc", fontFamily: "inherit", fontSize: 14, lineHeight: 1.5, color: "#16241d",
};

/** Nhu cầu thị trường — MÀN TIMELINE nhiều ngày (CHỈ hiện ngày đã có nhập, ngày trống tự ẩn) + sửa/thêm.
 *  Chuyên viên/admin: mọi đơn vị (cửa sổ editor, admin miễn). Đơn vị thành viên: CHỈ đơn vị được gán
 *  (đa đơn vị/1 tài khoản), cửa sổ member — dùng chung 1 component, đổi nguồn dữ liệu theo vai trò. */
export default function MarketDemandTimelinePage() {
  const { user, canEditCap, isUnitAccount, canEditUnitData } = useAuth();
  const isAdmin = user?.role === "admin";
  const isMember = isUnitAccount;   // nhập liệu + lãnh đạo: cùng nguồn dữ liệu của đơn vị

  const [days, setDays] = useState(90);
  const [data, setData] = useState<DemandTimeline | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState<string | null>(null); // "as_of|company"
  const [requesting, setRequesting] = useState(false);          // dòng đang sửa ở chế độ đề nghị
  const { saveOrRequest, modal } = useEditRequest();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [addForm, setAddForm] = useState({ as_of: todayISO(), company: "", content: "" });

  const load = useCallback((silent = false) => {
    if (!silent) setLoading(true);
    setErr("");
    (isMember ? fetchMyDemandTimeline(days) : fetchDemandTimeline(days))
      .then(setData).catch((e) => setErr(e.message)).finally(() => setLoading(false));
  }, [days, isMember]);
  useEffect(() => { load(); }, [load]);

  // Chuyên viên chỉ được cấp mức Xem → khoá ghi ở mọi ngày (đơn vị thành viên không xét cap).
  // Lãnh đạo đơn vị: chỉ xem.
  const mayEdit = canEditUnitData || canEditCap("market_demand");
  // Đơn vị đã SÁP NHẬP vào đơn vị của tài khoản: nội dung cũ vẫn hiện để tra cứu nhưng không sửa
  // được (server chặn) và cũng không cho chọn khi thêm mới.
  const viewOnly = useMemo(() => new Set(data?.view_only_units ?? []), [data]);
  const canEdit = (as_of: string, company: string) =>
    mayEdit && !viewOnly.has(company)
    && (isAdmin || (!!data && as_of <= data.today && daysBetween(data.today, as_of) <= data.edit_window_days));
  // Ngoài cửa sổ sửa (nhu cầu không bị chốt số liệu) → tài khoản đơn vị gửi đề nghị sửa để Ban duyệt.
  const canRequest = (as_of: string, company: string) =>
    canEditUnitData && !viewOnly.has(company) && !!data && as_of <= data.today && !canEdit(as_of, company);
  const startEdit = (e: DemandEntry, request: boolean) => {
    setEditing(`${e.as_of}|${e.company}`); setDraft(e.content); setRequesting(request);
  };

  // Gom entries theo ngày (đã sort DESC ở backend).
  const groups = useMemo(() => {
    const out: { as_of: string; items: DemandEntry[] }[] = [];
    for (const e of data?.entries ?? []) {
      const g = out[out.length - 1];
      if (g && g.as_of === e.as_of) g.items.push(e);
      else out.push({ as_of: e.as_of, items: [e] });
    }
    return out;
  }, [data]);

  // Server cho lưu thì lưu thẳng; tài khoản đơn vị bị cửa sổ sửa chặn thì popup gửi đề nghị.
  // Payload đề nghị = đúng thân API ghi thẳng (kể cả `create_only` của nút Thêm → Ban duyệt cũng chống ghi trùng).
  const doSave = async (
    company: string, as_of: string, content: string, key: string, after: () => void,
    createOnly = false, requestMode = false,
  ) => {
    setBusy(key);
    setErr("");
    try {
      const result = await saveOrRequest(
        () => (isMember ? saveMyDemand(company, as_of, content, createOnly) : saveDemand(company, as_of, content, createOnly)),
        { op: "market_demand", payload: { company, as_of, content, ...(createOnly ? { create_only: true } : {}) },
          title: `Nhu cầu thị trường ngày ${dmy(as_of)}`, company, dates: [as_of] });
      if (result === "cancelled") return;
      after();
      if (result === "saved") {
        if (requestMode) message.success(DIRECT_SAVED_IN_REQUEST_MODE);
        load(true);
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  // Chống ghi trùng: (ngày, đơn vị) đang chọn ở form Thêm đã có nhu cầu chưa (trong dữ liệu đã tải).
  const dupExists = useMemo(() =>
    !!addForm.company && (data?.entries ?? []).some(
      (e) => e.as_of === addForm.as_of && e.company === addForm.company && e.content.trim() !== ""),
    [data, addForm.company, addForm.as_of]);

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ApartmentOutlined style={{ marginRight: 8 }} />Nhu cầu thị trường</h2>
          <p>Ghi nhận <b>các lời chào hàng từ khách hàng, nhà sản xuất</b> và nhu cầu thị trường mà đơn vị
            nắm được — dùng để phân tích yếu tố <b>Cầu</b> trong quan hệ Cung – Cầu.</p>
          <p style={{ marginTop: 4 }}>{isMember
            ? "Nhập tự do theo ngày, trong cửa sổ cho phép — chỉ hiện những ngày đã có nhập."
            : "Tổng quan theo dòng thời gian của các đơn vị — chỉ hiện ngày đã có nhập."}</p>
        </div>
      </div>
      {err && <div className="blt-error">{err}</div>}

      <ReadOnlyNotice cap="market_demand" />

      <div className="card" style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
        <label className="blt-date-label">Khoảng thời gian:
          <select className="blt-date-input" style={{ marginLeft: 8 }} value={days}
            onChange={(e) => setDays(Number(e.target.value))}>
            {RANGES.map((d) => <option key={d} value={d}>{d} ngày gần nhất</option>)}
          </select>
        </label>
        {mayEdit && (
          <button className="btn btn-primary" onClick={() => setAdding((a) => !a)}
            style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 6 }}>
            <PlusOutlined /> Thêm nhu cầu
          </button>
        )}
      </div>

      {adding && (
        <div className="card" style={{ display: "grid", gap: 10 }}>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
            <label className="blt-date-label">Ngày:
              <DateInput value={addForm.as_of} onChange={(v) => setAddForm((f) => ({ ...f, as_of: v }))} noFuture style={{ marginLeft: 8 }} />
            </label>
            <Select showSearch placeholder="Chọn đơn vị" style={{ minWidth: 240 }}
              value={addForm.company || undefined}
              onChange={(v) => setAddForm((f) => ({ ...f, company: v }))}
              options={(data?.units ?? []).filter((u) => !viewOnly.has(u))
                .map((u) => ({ value: u, label: u }))}
              filterOption={(i, o) => (o?.label ?? "").toLowerCase().includes(i.toLowerCase())} />
          </div>
          {dupExists && (
            <div style={{ color: "#b45309", background: "#fef3c7", padding: "8px 12px", borderRadius: 8, fontSize: 13 }}>
              Đơn vị này đã có nhu cầu cho ngày này — hãy bấm nút Sửa ở dòng tương ứng thay vì tạo mới.
            </div>
          )}
          <textarea value={addForm.content} rows={6} style={taStyle}
            placeholder={"Mỗi nhu cầu ghi 1 dòng, nêu rõ: khách hàng/nhà sản xuất · chủng loại · số lượng · mức giá chào · thời điểm giao hàng. Ví dụ:\n"
              + "1. Công ty ... hỏi mua hàng ... với giá 50tr, giao tại ..., thời gian ...\n"
              + "2. Công ty ..."}
            onChange={(e) => setAddForm((f) => ({ ...f, content: e.target.value }))} />
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary"
              disabled={!addForm.company || !addForm.content.trim() || dupExists || busy === "add"}
              onClick={() => doSave(addForm.company, addForm.as_of, addForm.content, "add",
                () => { setAdding(false); setAddForm({ as_of: todayISO(), company: "", content: "" }); }, true)}>
              {busy === "add" ? <span className="spinner" /> : "Lưu"}
            </button>
            <button className="btn" onClick={() => setAdding(false)}>Huỷ</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="blt-loading"><span className="spinner" /> Đang tải…</div>
      ) : groups.length === 0 ? (
        <div className="card"><div className="scan-empty">Chưa có nhu cầu nào được nhập trong khoảng này.</div></div>
      ) : (
        <div style={{ display: "grid", gap: 14 }}>
          {groups.map((g) => (
            <div key={g.as_of}>
              <div style={{ fontWeight: 700, color: "#0a9e48", margin: "2px 0 6px", fontSize: 15 }}>
                {dmy(g.as_of)}<span style={{ color: "var(--muted)", fontWeight: 400, fontSize: 13 }}> · {g.items.length} đơn vị</span>
              </div>
              <div className="card" style={{ padding: "2px 14px" }}>
                {g.items.map((e, i) => {
                  const key = `${e.as_of}|${e.company}`;
                  const isEditing = editing === key;
                  return (
                    <div key={key} style={{ padding: "9px 0", borderTop: i ? "1px solid #eef2ee" : "none" }}>
                      {isEditing ? (
                        <>
                          <div style={{ fontWeight: 600, color: "#0a9e48", marginBottom: 6 }}>{e.company}</div>
                          {requesting && (
                            <Alert type="warning" showIcon style={{ marginBottom: 6 }}
                              message="Bạn đang soạn đề nghị sửa — số liệu chỉ thay đổi sau khi Ban duyệt." />
                          )}
                          <textarea value={draft} rows={3} style={taStyle} onChange={(ev) => setDraft(ev.target.value)} />
                          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                            <button className="btn btn-primary" disabled={busy === key}
                              onClick={() => doSave(e.company, e.as_of, draft, key, () => setEditing(null), false, requesting)}>
                              {busy === key ? <span className="spinner" />
                                : requesting ? <><SendOutlined /> Gửi đề nghị sửa</> : "Lưu"}
                            </button>
                            <button className="btn" onClick={() => setEditing(null)}>Huỷ</button>
                          </div>
                        </>
                      ) : (
                        <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                          <div style={{ flex: 1, fontSize: 14, lineHeight: 1.5, color: "#16241d" }}>
                            <b style={{ color: "#0a9e48" }}>{e.company}:</b> {e.content}
                          </div>
                          {canRequest(e.as_of, e.company) && (
                            <button className="btn" style={{ flex: "0 0 auto", fontSize: 12, padding: "3px 8px" }}
                              title="Ngày này đã ngoài cửa sổ sửa — gửi đề nghị để Ban duyệt"
                              onClick={() => startEdit(e, true)}>
                              <FormOutlined /> Đề nghị sửa
                            </button>
                          )}
                          {canEdit(e.as_of, e.company) && (
                            <button onClick={() => startEdit(e, false)} title="Sửa"
                              style={{ flex: "0 0 auto", border: "none", background: "none", cursor: "pointer",
                                color: "var(--muted)", padding: 2, fontSize: 14, lineHeight: 1 }}>
                              <EditOutlined />
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
      {modal}
    </div>
  );
}
