/* Kế hoạch năm — số liệu lớn NHẬP 1 LẦN cho cả năm (không nhập hàng ngày), cập nhật khi có thay đổi:
   kế hoạch khai thác (cột đầu) + kế hoạch thu mua năm + kế hoạch hàng hóa + tổng sản lượng đã ký
   hợp đồng dài hạn…
   Đơn vị thành viên: chỉ đơn vị của mình · Chuyên viên có quyền `unit_daily`: mọi đơn vị.
   Tài khoản nhập liệu đơn vị chỉ sửa ô thuộc loại được giao: ô thu mua ↔ Thu mua, các ô còn lại ↔
   Hợp đồng & tiêu thụ (server bỏ qua ô ngoài loại, giữ nguyên số đã lưu).
   Kế hoạch CHỐT CÙNG ĐỢT chốt số liệu (03/10/2026): đơn vị đã chốt tới năm này thì ô chỉ xem, sửa
   bằng «Đề nghị sửa» (mở dòng → sửa số → gửi; Ban duyệt mới ghi). Chuyên viên vẫn sửa thẳng. */

import { ProfileOutlined } from "@ant-design/icons";
import { Select, Spin } from "antd";
import { useMemo, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import { ENTRY_TYPE_LABEL, type EntryType } from "../../../lib/entry-types";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import type { Role, YearPlanRow } from "../../../lib/unit-daily-client";
import { fmtNum } from "../../../lib/unit-daily-fields";
import ExcelImportBar from "./components/ExcelImportBar";
import YearPlanLockCell, { YearPlanLockBanner } from "./components/YearPlanLockCell";
import { numInput } from "./unit-daily-inputs";
import { PLAN_FIELDS, fieldEntryType } from "./year-plan-fields";
import { useYearPlan } from "./useYearPlan";
import "../../bulletin/bulletin.css";

const YEARS = 6; // năm hiện tại + 2 năm trước/sau để chọn

export default function YearPlanPage() {
  const { user, isUnitAccount, canEditUnitData, canEditCap, hasEntryType } = useAuth();
  const role: Role = isUnitAccount ? "member" : "hq";
  // Chuyên viên chỉ được cấp mức Xem → khoá ô nhập (đơn vị thành viên không xét cap).
  // Lãnh đạo đơn vị: chỉ xem.
  const canEdit = canEditUnitData || canEditCap("unit_daily");
  const isMember = user?.role === "member";
  const canEditField = (key: keyof YearPlanRow) =>
    canEdit && (!isMember || hasEntryType(fieldEntryType(key)));
  // Ô ngoài phần việc của tài khoản nhập liệu (vd chuyên viên Thu mua nhìn ô hợp đồng) → báo rõ.
  const lockedTypes = isMember
    ? (["purchase", "contract"] as EntryType[]).filter((t) => !hasEntryType(t)) : [];
  const thisYear = new Date().getFullYear();
  const [year, setYear] = useState(thisYear);
  const {
    units, lockedUntil, requesting, setRequesting, loading, savingUnit, load, rowOf, setCell,
    cellEditable, rowLocked, save, sendRequest, cancelRequest, anyLocked, modal,
  } = useYearPlan(role, year, canEditField);

  const yearOpts = useMemo(
    () => Array.from({ length: YEARS }, (_, i) => thisYear - 2 + i).map((y) => ({ value: y, label: `Năm ${y}` })),
    [thisYear],
  );

  const total = (key: keyof YearPlanRow) =>
    units.reduce((a, u) => a + (rowOf(u)[key] ?? 0), 0) || null;

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ProfileOutlined style={{ marginRight: 8 }} />Kế hoạch năm</h2>
          <p>
            Số liệu cả năm — <b>nhập 1 lần</b>, chỉ cập nhật khi có thay đổi (không nhập hàng ngày).
            Đơn vị có <b>kế hoạch thu mua &gt; 0</b> thì mới hiện màn <b>Báo cáo thu mua</b>; để trống
            hoặc <b>0</b> = đơn vị không tổ chức thu mua.
            {role === "member" ? " Chỉ hiện đơn vị của bạn." : " Xem/sửa mọi đơn vị."}
          </p>
          {canEdit && lockedTypes.length > 0 && (
            <p>
              Ô thuộc phần việc {lockedTypes.map((t) => `"${ENTRY_TYPE_LABEL[t]}"`).join(", ")} chỉ xem —
              tài khoản của bạn không được giao loại nhập liệu này.
            </p>
          )}
        </div>
      </div>

      <ReadOnlyNotice cap="unit_daily" />
      {anyLocked && <YearPlanLockBanner year={year} lockedUntil={units.map((u) => lockedUntil[u]).find(Boolean) ?? null} />}

      <div className="blt-toolbar" style={{ marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--muted)" }}>Năm:</span>
        <Select value={year} onChange={setYear} options={yearOpts} style={{ width: 140 }} />
        <span style={{ color: "var(--muted)", fontSize: 13 }}>{units.length} đơn vị</span>
        <ExcelImportBar kind="plan" role={role} label="Kế hoạch năm" onDone={load} />
      </div>
      {/* Tân Biên 29/09/2026: gộp hàng hóa vào thu mua thì sai chỉ tiêu thu mua, bỏ trống thì KH bán
          hàng thiếu phần hàng hóa → mỗi nguồn một ô. */}
      <p className="form-note" style={{ margin: "0 0 12px" }}>
        Kế hoạch bán hàng = khai thác + thu mua + hàng hóa. <b>Thu mua</b> chỉ gồm mủ nguyên liệu (mủ
        nước, mủ chén, mủ dây — quy khô). <b>Hàng hóa</b> là thành phẩm mua của đơn vị khác để bán lại —
        nhập vào ô riêng, không cộng vào thu mua. Không kinh doanh hàng hóa thì nhập 0.
      </p>

      <Spin spinning={loading}>
        <div className="card" style={{ padding: 0, overflow: "auto" }}>
          <table>
            <thead>
              <tr>
                <th style={{ width: 60 }}>#</th>
                <th>Đơn vị</th>
                {PLAN_FIELDS.map((f) => (
                  <th key={f.key} className="r" style={{ width: f.width }}>{f.title}</th>
                ))}
                {anyLocked && <th style={{ width: 210 }}>Chốt số liệu</th>}
              </tr>
            </thead>
            <tbody>
              {units.map((u, i) => {
                const r = rowOf(u);
                return (
                  <tr key={u} style={{ opacity: savingUnit === u ? 0.6 : 1 }}>
                    <td>{i + 1}</td>
                    <td style={{ fontWeight: 500 }}>{u}</td>
                    {PLAN_FIELDS.map(({ key }) => (
                      <td key={key} onBlur={() => cellEditable(u, key) && save(u)}>
                        {numInput(r[key], (v) => setCell(u, key, v), !cellEditable(u, key))}
                      </td>
                    ))}
                    {anyLocked && (
                      <td>
                        <YearPlanLockCell locked={rowLocked(u)} lockedUntil={lockedUntil[u] ?? null}
                          canRequest={canEdit} requesting={requesting === u} busy={savingUnit === u}
                          onStart={() => setRequesting(u)} onSend={() => sendRequest(u)}
                          onCancel={() => cancelRequest(u)} />
                      </td>
                    )}
                  </tr>
                );
              })}
              {units.length === 0 && !loading && (
                <tr><td colSpan={PLAN_FIELDS.length + (anyLocked ? 3 : 2)}
                  style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                  Chưa có đơn vị nào.
                </td></tr>
              )}
              {units.length > 1 && (
                <tr style={{ fontWeight: 600, background: "rgba(125,125,125,.08)" }}>
                  <td />
                  <td>Tổng cộng</td>
                  {PLAN_FIELDS.map(({ key }) => <td key={key} className="r">{fmtNum(total(key), 3)}</td>)}
                  {anyLocked && <td />}
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Spin>
      {modal}
    </div>
  );
}
