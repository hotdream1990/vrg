import { FundOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  type PhysicalSheet,
  deletePhysicalDate,
  fetchPhysicalSheet,
  upsertRecord,
} from "../../../lib/api-client";
import { useAuth } from "../../auth/AuthContext";
import DateRangeBar from "../sections/DateRangeBar";
import EditableCell from "../sections/EditableCell";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import "../../bulletin/bulletin.css";

const todayISO = () => new Date().toISOString().slice(0, 10);
const STICKY = { position: "sticky" as const, left: 0, background: "var(--card, #0d1117)", zIndex: 1 };

/** Quản lý số liệu → Giá Physical (giao ngay): lưới hàng=ngày × cột=grade (RSS3/STR20/SMR20…). */
export default function PhysicalSheetPage() {
  const { canEdit } = useAuth();
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
    const set = new Set([...extraDates, ...(sheet?.dates ?? [])]);
    return [...set].sort().reverse();
  }, [sheet, extraDates]);
  const grades = sheet?.grades ?? [];

  // Nhập tay lưu nguồn 'reuters', USD/tonne (đơn vị dữ liệu cũ có thể lẫn — xem ghi chú).
  const saveCell = (grade: string, date: string, price: number) =>
    upsertRecord({ as_of: date, source: "reuters", grade, contract: "",
      price_type: "physical", price, currency: "USD", unit: "USD/tonne" })
      .then(load).catch((e) => setErr(e.message));

  const addDate = () => {
    if (newDate && !dates.includes(newDate)) setExtraDates((d) => [...new Set([...d, newDate])]);
  };
  const delDate = (d: string) => {
    if (!confirm(`Xoá toàn bộ giá physical ngày ${d}?`)) return;
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

      <ReadOnlyNotice />

      <DateRangeBar from={from} to={to} onFrom={setFrom} onTo={setTo} onReload={load}
        info={`${dates.length} ngày · ${grades.length} grade`}>
        {canEdit && (
          <>
            <label className="blt-date-label">Thêm ngày:
              <input type="date" className="blt-date-input" value={newDate}
                onChange={(e) => setNewDate(e.target.value)} />
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
            {dates.map((d) => (
              <tr key={d}>
                <td style={{ ...STICKY, whiteSpace: "nowrap", fontWeight: 500 }}>
                  {d}{" "}
                  {canEdit && (
                    <button className="blt-rm-btn" title="Xoá ngày" onClick={() => delDate(d)}
                      style={{ fontSize: 11 }}>✕</button>
                  )}
                </td>
                {grades.map((g) => (
                  <td key={g} className="r">
                    <EditableCell value={sheet?.values[g]?.[d] ?? null} onSave={(n) => saveCell(g, d, n)} readOnly={!canEdit} />
                  </td>
                ))}
              </tr>
            ))}
            {dates.length === 0 && (
              <tr><td colSpan={grades.length + 1} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                {canEdit ? 'Chưa có ngày nào — chọn ngày rồi bấm "＋ Thêm ngày" để nhập.' : "Chưa có dữ liệu."}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 8 }}>
        Đơn vị: USD/tấn (chuỗi Reuters, đã quy đổi sẵn). Lịch sử 14/05/2024 → 29/12/2025 nạp từ Excel chuyên viên;
        số liệu mới <b>nhập tay trực tiếp tại đây</b> — chọn ngày rồi bấm ô để nhập.
      </p>
    </div>
  );
}
