import { ExperimentOutlined, SyncOutlined, TeamOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  type PurchaseSheet,
  deletePurchaseDate,
  deleteRecord,
  fetchPurchaseSheet,
  upsertRecord,
} from "../../../lib/api-client";
import { buildGridPrevMap } from "../../../lib/change-warning";
import { dmy, todayISO } from "../../../lib/date";
import { useEditorWindow } from "../../../lib/edit-window";
import { type AutoSyncConfig, fetchAutoSync } from "../../../lib/purchase-auto-sync-client";
import { useAuth } from "../../auth/AuthContext";
import DateInput from "../sections/DateInput";
import DataSourceNote from "../sections/DataSourceNote";
import DateRangeBar from "../sections/DateRangeBar";
import EditableCell from "../sections/EditableCell";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import PurchaseAutoSyncModal from "./components/PurchaseAutoSyncModal";
import "../../bulletin/bulletin.css";

const STICKY = { position: "sticky" as const, left: 0, background: "var(--card, #0d1117)", zIndex: 1 };

/** Quản lý số liệu → Giá mủ nguyên liệu: lưới hàng=ngày × cột=đơn vị (đồng/độ TSC). */
export default function RawMaterialPage() {
  const { canEditCap } = useAuth();
  const canEdit = canEditCap("raw_material"); // mức Xem của mục này → khoá toàn bộ thao tác ghi
  const ew = useEditorWindow(); // cửa sổ sửa: ngày cũ hơn N ngày → chỉ xem (admin miễn)
  const [sheet, setSheet] = useState<PurchaseSheet | null>(null);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [newDate, setNewDate] = useState(todayISO());
  const [extraDates, setExtraDates] = useState<string[]>([]);
  const [err, setErr] = useState("");
  // Cầu tự động: đơn vị nào đang để số tự khai chảy thẳng vào lưới này (xem PurchaseAutoSyncModal).
  const [auto, setAuto] = useState<AutoSyncConfig | null>(null);
  const [syncOpen, setSyncOpen] = useState(false);

  const load = useCallback(() => {
    setErr("");
    fetchPurchaseSheet(from || undefined, to || undefined).then(setSheet).catch((e) => setErr(e.message));
  }, [from, to]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { fetchAutoSync().then(setAuto).catch(() => setAuto(null)); }, []);

  // Tên các đơn vị đang lấy số tự động — đánh dấu ngay trên đầu cột để không ai sửa tay nhầm.
  const autoNames = useMemo(
    () => new Set(auto?.enabled ? auto.units.filter((u) => u.auto).map((u) => u.name) : []),
    [auto]);

  // Hàng = ngày trong cửa sổ sửa (hiện sẵn để nhập) + ngày có data + ngày vừa "Thêm" (mới nhất trước).
  const dates = useMemo(() => {
    const set = new Set([...ew.windowDates, ...extraDates, ...(sheet?.dates ?? [])]);
    return [...set].sort().reverse();
  }, [sheet, extraDates, ew.windowDates]);
  const companies = sheet?.companies ?? [];
  // prev[company][date] = giá ngày trước để cảnh báo lệch ≥10% khi nhập tay.
  const prevOf = useMemo(() => buildGridPrevMap(companies, dates, sheet?.values), [companies, dates, sheet]);

  const saveCell = (company: string, date: string, price: number) =>
    upsertRecord({ as_of: date, source: "vrg", grade: company, contract: "",
      price_type: "purchase", price, currency: "VND", unit: "đồng/độ TSC" })
      .then(load).catch((e) => setErr(e.message));

  // Xoá trắng 1 ô → xoá bản ghi giá thu mua của đúng (đơn vị, ngày) đó.
  const clearCell = (company: string, date: string) =>
    deleteRecord({ as_of: date, source: "vrg", grade: company, contract: "", price_type: "purchase" })
      .then(load).catch((e) => setErr(e.message));

  const addDate = () => {
    if (!newDate || dates.includes(newDate)) return;
    if (!ew.isEditable(newDate)) {
      setErr(`Ngày ${dmy(newDate)} đã ngoài cửa sổ sửa — chỉ nhập được ${ew.days ?? 7} ngày gần nhất.`);
      return;
    }
    setExtraDates((d) => [...new Set([...d, newDate])]);
  };
  const delDate = (d: string) => {
    if (!confirm(`Xoá toàn bộ giá thu mua ngày ${dmy(d)}?`)) return;
    deletePurchaseDate(d)
      .then(() => { setExtraDates((x) => x.filter((e) => e !== d)); load(); })
      .catch((e) => setErr(e.message));
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ExperimentOutlined style={{ marginRight: 8 }} />Giá mủ nguyên liệu</h2>
          <p>
            Giá thu mua mủ nước theo đơn vị thành viên VRG (đồng/độ TSC) — hàng là ngày, cột là đơn vị. Bấm ô để sửa.
            Đây là <b>số của chuyên viên chốt</b>, dùng cho bản tin và báo cáo; số các đơn vị tự khai
            nằm riêng, xem ở <Link to="/thong-ke/thu-mua">Thống kê thu mua</Link>.
          </p>
        </div>
        <div className="actions">
          {/* Mức Xem vẫn mở được để biết lưới đang được máy đổ số từ đơn vị nào (modal tự khoá ghi). */}
          <button className="btn" onClick={() => setSyncOpen(true)}>
            <SyncOutlined style={{ marginRight: 6 }} />Tự động lấy số từ đơn vị
          </button>
          {canEdit && (
            <Link className="btn" to="/quan-ly-so-lieu/don-vi-thanh-vien"><TeamOutlined style={{ marginRight: 6 }} />Quản lý đơn vị</Link>
          )}
        </div>
      </div>

      {autoNames.size > 0 && (
        <div className="chip" style={{ marginBottom: 8 }}>
          <SyncOutlined style={{ marginRight: 6 }} />
          Đang <b>tự động lấy số</b> của {autoNames.size} đơn vị — các đơn vị đó nhập là số vào
          thẳng lưới này; cột của họ có dấu đồng bộ ở đầu.
        </div>
      )}

      <ReadOnlyNotice cap="raw_material" />
      <DataSourceNote page="raw-material" />

      <DateRangeBar from={from} to={to} onFrom={setFrom} onTo={setTo} onReload={load}
        info={`${dates.length} ngày · ${companies.length} đơn vị`}>
        {canEdit && (
          <>
            <label className="blt-date-label">Thêm ngày:
              <DateInput value={newDate} onChange={setNewDate} />
            </label>
            <button className="btn btn-primary" onClick={addDate}>＋ Thêm ngày</button>
          </>
        )}
      </DateRangeBar>

      {err && <div className="blt-error">{err}</div>}

      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table style={{ fontSize: 12 }}>
          <thead>
            <tr>
              <th style={STICKY}>Ngày</th>
              {companies.map((co) => (
                <th key={co} className="r" style={{ whiteSpace: "nowrap" }}>
                  {autoNames.has(co) && (
                    <SyncOutlined style={{ marginRight: 4 }}
                      title="Đang lấy số tự động từ đơn vị — sửa tay sẽ bị ghi đè ở lần đơn vị nộp sau" />
                  )}
                  {co}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dates.map((d) => {
              const ed = ew.isEditable(d);
              const hasData = companies.some((co) => sheet?.values[co]?.[d] != null);
              return (
              <tr key={d}>
                <td style={{ ...STICKY, whiteSpace: "nowrap", fontWeight: 500 }}>
                  {dmy(d)}{" "}
                  {canEdit && ed && hasData && (
                    <button className="blt-rm-btn" title="Xoá ngày" onClick={() => delDate(d)}
                      style={{ fontSize: 11 }}>✕</button>
                  )}
                  {canEdit && !ed && <span style={{ color: "var(--muted)", fontSize: 11 }}>(chỉ xem)</span>}
                </td>
                {companies.map((co) => (
                  <td key={co} className="r">
                    <EditableCell value={sheet?.values[co]?.[d] ?? null} prevValue={prevOf[co]?.[d]}
                      onSave={(n) => saveCell(co, d, n)} onClear={() => clearCell(co, d)} readOnly={!canEdit || !ed} />
                  </td>
                ))}
              </tr>
              );
            })}
            {dates.length === 0 && (
              <tr><td colSpan={companies.length + 1} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                {canEdit ? 'Chưa có ngày nào — chọn ngày rồi bấm "＋ Thêm ngày" để nhập.' : "Chưa có dữ liệu."}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {syncOpen && (
        <PurchaseAutoSyncModal readOnly={!canEdit} onClose={() => setSyncOpen(false)}
          onSaved={(cfg) => { setAuto(cfg); load(); }} />
      )}
    </div>
  );
}
