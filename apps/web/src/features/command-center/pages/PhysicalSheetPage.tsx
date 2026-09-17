import { FundOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  type PhysicalSheet,
  deletePhysicalDate,
  deleteRecord,
  fetchPhysicalSheet,
  upsertRecord,
} from "../../../lib/api-client";
import { buildGridPrevMap } from "../../../lib/change-warning";
import { dmy, todayISO } from "../../../lib/date";
import { useEditorWindow, windowPhrase } from "../../../lib/edit-window";
import { useAuth } from "../../auth/AuthContext";
import DateInput from "../sections/DateInput";
import DataSourceNote from "../sections/DataSourceNote";
import DateRangeBar from "../sections/DateRangeBar";
import EditableCell from "../sections/EditableCell";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import ReutersPasteImport from "./components/ReutersPasteImport";
import "../../bulletin/bulletin.css";

const STICKY = { position: "sticky" as const, left: 0, background: "var(--card, #0d1117)", zIndex: 1 };

/** Quản lý số liệu → Giá Physical (giao ngay): lưới hàng=ngày × cột=grade (RSS3/STR20/SMR20…). */
export default function PhysicalSheetPage() {
  const { canEditCap } = useAuth();
  const canEdit = canEditCap("physical"); // mức Xem của mục này → khoá toàn bộ thao tác ghi
  const ew = useEditorWindow(); // cửa sổ sửa: ngày cũ hơn N ngày → chỉ xem (admin miễn)
  const [sheet, setSheet] = useState<PhysicalSheet | null>(null);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [newDate, setNewDate] = useState(todayISO());
  const [extraDates, setExtraDates] = useState<string[]>([]);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setErr("");
    fetchPhysicalSheet(from || undefined, to || undefined).then(setSheet).catch((e) => setErr(e.message));
  }, [from, to]);
  useEffect(() => { load(); }, [load]);

  const dates = useMemo(() => {
    const set = new Set([...ew.windowDates, ...extraDates, ...(sheet?.dates ?? [])]);
    return [...set].sort().reverse();
  }, [sheet, extraDates, ew.windowDates]);
  const grades = sheet?.grades ?? [];
  // prev[grade][date] = giá ngày trước để cảnh báo lệch ≥10% khi nhập tay.
  const prevOf = useMemo(() => buildGridPrevMap(grades, dates, sheet?.values), [grades, dates, sheet]);

  // Nhập tay lưu nguồn 'reuters', USD/tonne (đơn vị dữ liệu cũ có thể lẫn — xem ghi chú).
  const saveCell = (grade: string, date: string, price: number) =>
    upsertRecord({ as_of: date, source: "reuters", grade, contract: "",
      price_type: "physical", price, currency: "USD", unit: "USD/tonne" })
      .then(load).catch((e) => setErr(e.message));

  // Xoá trắng 1 ô → xoá bản ghi giá của đúng (grade, ngày) đó.
  const clearCell = (grade: string, date: string) =>
    deleteRecord({ as_of: date, source: "reuters", grade, contract: "", price_type: "physical" })
      .then(load).catch((e) => setErr(e.message));

  const addDate = () => {
    if (!newDate || dates.includes(newDate)) return;
    if (!ew.isEditable(newDate)) {
      setErr(`Ngày ${dmy(newDate)} đã ngoài cửa sổ sửa — chỉ nhập được ${windowPhrase(ew.days ?? 7)}.`);
      return;
    }
    setExtraDates((d) => [...new Set([...d, newDate])]);
  };
  const delDate = (d: string) => {
    if (!confirm(`Xoá toàn bộ giá physical ngày ${dmy(d)}?`)) return;
    deletePhysicalDate(d)
      .then(() => { setExtraDates((x) => x.filter((e) => e !== d)); load(); })
      .catch((e) => setErr(e.message));
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><FundOutlined style={{ marginRight: 8 }} />Giá Physical</h2>
          <p>Giá giao ngay (Asian physical) theo grade, <b>USD/tấn</b> — hàng là ngày, cột là chủng loại. Bấm ô để sửa.</p>
        </div>
      </div>

      <ReadOnlyNotice cap="physical" />
      <DataSourceNote page="physical" />

      {canEdit && <ReutersPasteImport defaultDate={newDate} onImported={load} />}

      <DateRangeBar from={from} to={to} onFrom={setFrom} onTo={setTo} onReload={load}
        info={`${dates.length} ngày · ${grades.length} grade`}>
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
              {grades.map((g) => (
                <th key={g} className="r" style={{ whiteSpace: "nowrap" }}>{g}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dates.map((d) => {
              const ed = ew.isEditable(d);
              const hasData = grades.some((g) => sheet?.values[g]?.[d] != null);
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
                {grades.map((g) => (
                  <td key={g} className="r">
                    <EditableCell value={sheet?.values[g]?.[d] ?? null} prevValue={prevOf[g]?.[d]}
                      onSave={(n) => saveCell(g, d, n)} onClear={() => clearCell(g, d)} readOnly={!canEdit || !ed} />
                  </td>
                ))}
              </tr>
              );
            })}
            {dates.length === 0 && (
              <tr><td colSpan={grades.length + 1} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                {canEdit ? 'Chưa có ngày nào — chọn ngày rồi bấm "＋ Thêm ngày" để nhập.' : "Chưa có dữ liệu."}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="form-note" style={{ fontSize: 12, marginTop: 8 }}>
        Đơn vị: USD/tấn (chuỗi Reuters, đã quy đổi sẵn). Lịch sử 14/05/2024 → 29/12/2025 nạp từ Excel chuyên viên;
        số liệu mới <b>nhập tay trực tiếp tại đây</b> — chọn ngày rồi bấm ô để nhập.
      </p>
    </div>
  );
}
