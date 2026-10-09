/* Kế hoạch năm — số liệu lớn NHẬP 1 LẦN cho cả năm (không nhập hàng ngày), cập nhật khi có thay đổi.
   Từ 09/10/2026: 7 nhóm · 23 chỉ tiêu (khai thác · thu mua · chế biến · tiêu thụ · doanh thu · tồn kho
   thành phẩm cuối năm · hợp đồng), bảng ĐẢO — mỗi chỉ tiêu một hàng, mỗi đơn vị một cột (YearPlanGrid).
   Đơn vị chỉ nhập mục con; dòng tổng tự cộng (tổng doanh thu do server cộng và lưu).
   Đơn vị thành viên: chỉ đơn vị của mình · Chuyên viên có quyền `unit_daily`: mọi đơn vị.
   Tài khoản nhập liệu đơn vị chỉ sửa ô thuộc loại được giao: ô thu mua nguyên liệu ↔ Thu mua, các ô còn
   lại ↔ Hợp đồng & tiêu thụ (server bỏ qua ô ngoài loại, giữ nguyên số đã lưu).
   Kế hoạch CHỐT CÙNG ĐỢT chốt số liệu (03/10/2026): đơn vị đã chốt tới năm này thì cột chỉ xem, sửa
   bằng «Đề nghị sửa» ở đầu cột (mở cột → sửa số → gửi; Ban duyệt mới ghi). Chuyên viên vẫn sửa thẳng. */

import { ProfileOutlined } from "@ant-design/icons";
import { Select, Spin } from "antd";
import { useMemo, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import { ENTRY_TYPE_LABEL, type EntryType } from "../../../lib/entry-types";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import type { Role, YearPlanRow } from "../../../lib/unit-daily-client";
import ExcelImportBar from "./components/ExcelImportBar";
import YearPlanLockCell, { YearPlanLockBanner } from "./components/YearPlanLockCell";
import { PLAN_FIELD_BY_KEY, fieldEntryType } from "./year-plan-fields";
import YearPlanGrid from "./YearPlanGrid";
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
  // Ô tự tính (tổng doanh thu) không ai gõ được — server cộng từ 3 mục con.
  const canEditField = (key: keyof YearPlanRow) =>
    canEdit && !PLAN_FIELD_BY_KEY[key]?.derived && (!isMember || hasEntryType(fieldEntryType(key)));
  // Ô ngoài phần việc của tài khoản nhập liệu (vd chuyên viên Thu mua nhìn ô hợp đồng) → báo rõ.
  const lockedTypes = isMember
    ? (["purchase", "contract"] as EntryType[]).filter((t) => !hasEntryType(t)) : [];
  const thisYear = new Date().getFullYear();
  const [year, setYear] = useState(thisYear);
  const {
    units, lockedUntil, requesting, setRequesting, loading, savingUnit, load, rowOf, setCell,
    cellEditable, rowLocked, saveOnLeave, sendRequest, cancelRequest, anyLocked, modal,
  } = useYearPlan(role, year, canEditField);

  const yearOpts = useMemo(
    () => Array.from({ length: YEARS }, (_, i) => thisYear - 2 + i).map((y) => ({ value: y, label: `Năm ${y}` })),
    [thisYear],
  );

  const lockHead = (u: string) => (
    <YearPlanLockCell locked={rowLocked(u)} lockedUntil={lockedUntil[u] ?? null}
      canRequest={canEdit} requesting={requesting === u} busy={savingUnit === u}
      onStart={() => setRequesting(u)} onSend={() => sendRequest(u)} onCancel={() => cancelRequest(u)} />
  );

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ProfileOutlined style={{ marginRight: 8 }} />Kế hoạch năm</h2>
          <p>Nhập một lần cho cả năm, chỉ sửa khi có thay đổi.</p>
          {canEdit && lockedTypes.length > 0 && (
            <p>
              Chỉ xem các ô thuộc {lockedTypes.map((t) => `«${ENTRY_TYPE_LABEL[t]}»`).join(", ")} — tài khoản chưa được giao loại nhập liệu này.
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
      <Spin spinning={loading}>
        {units.length === 0 && !loading
          ? <div className="card" style={{ textAlign: "center", color: "var(--muted)" }}>Chưa có đơn vị nào.</div>
          : (
            <YearPlanGrid units={units} rowOf={rowOf} setCell={setCell} cellEditable={cellEditable}
              onLeave={saveOnLeave} savingUnit={savingUnit} unitHeadExtra={anyLocked ? lockHead : undefined} />
          )}
      </Spin>
      {modal}
    </div>
  );
}
