/* Kế hoạch năm — số liệu lớn NHẬP 1 LẦN cho cả năm (không nhập hàng ngày), cập nhật khi có thay đổi:
   kế hoạch khai thác (cột đầu) + kế hoạch thu mua năm + kế hoạch hàng hóa + tổng sản lượng đã ký
   hợp đồng dài hạn…
   Đơn vị thành viên: chỉ đơn vị của mình · Chuyên viên có quyền `unit_daily`: mọi đơn vị.
   Tài khoản nhập liệu đơn vị chỉ sửa ô thuộc loại được giao: ô thu mua ↔ Thu mua, các ô còn lại ↔
   Hợp đồng & tiêu thụ (server bỏ qua ô ngoài loại, giữ nguyên số đã lưu). */

import { ProfileOutlined } from "@ant-design/icons";
import { Select, Spin, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import { ENTRY_TYPE_LABEL, type EntryType } from "../../../lib/entry-types";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import { type Role, type YearPlanRow, fetchYearPlan, saveYearPlan } from "../../../lib/unit-daily-client";
import { fmtNum } from "../../../lib/unit-daily-fields";
import ExcelImportBar from "./components/ExcelImportBar";
import { numInput } from "./unit-daily-inputs";
import "../../bulletin/bulletin.css";

const YEARS = 6; // năm hiện tại + 2 năm trước/sau để chọn

type PlanField = { key: keyof YearPlanRow; title: string; width: number };

const PLAN_FIELDS: PlanField[] = [
  // Khai thác = mủ từ vườn cây của chính đơn vị; thu mua = mua của dân → 2 chỉ tiêu riêng.
  { key: "plan_exploit_tonnes", title: "Kế hoạch khai thác (tấn)", width: 220 },
  { key: "plan_tonnes", title: "Kế hoạch thu mua (tấn)", width: 240 },
  { key: "plan_goods_tonnes", title: "Kế hoạch hàng hóa — thành phẩm mua ngoài (tấn)", width: 240 },
  { key: "plan_sales_spot_tonnes", title: "Kế hoạch tiêu thụ — HĐ chuyến (tấn)", width: 240 },
  { key: "signed_lt_tonnes", title: "HĐ dài hạn đã ký (tấn)", width: 220 },
  { key: "carry_lt_tonnes", title: "HĐ dài hạn 2025 chuyển sang (tấn)", width: 220 },
  { key: "carry_spot_tonnes", title: "HĐ chuyến 2025 chuyển sang (tấn)", width: 220 },
  // Ô TIỀN duy nhất của bảng — ghi rõ TỶ ĐỒNG ngay trên tiêu đề, cột còn lại đều là tấn nên không
  // ghi thì chắc chắn có người nhập nhầm sang tấn.
  { key: "plan_revenue_ty", title: "Kế hoạch doanh thu (tỷ đồng)", width: 220 },
];

/** Loại nhập liệu phụ trách từng ô (khớp backend `PUT /api/member/plan`). */
const fieldEntryType = (key: keyof YearPlanRow): EntryType => (key === "plan_tonnes" ? "purchase" : "contract");

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
  const [units, setUnits] = useState<string[]>([]);
  const [plans, setPlans] = useState<Record<string, YearPlanRow>>({});
  const [loading, setLoading] = useState(false);
  const [savingUnit, setSavingUnit] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchYearPlan(role, year)
      .then((d) => { setUnits(d.units); setPlans(d.plans ?? {}); })
      .catch((e) => message.error(e.message))
      .finally(() => setLoading(false));
  }, [role, year]);
  useEffect(() => { load(); }, [load]);

  const EMPTY: YearPlanRow = { plan_exploit_tonnes: null, plan_tonnes: null, plan_goods_tonnes: null,
    plan_sales_spot_tonnes: null,
    signed_lt_tonnes: null, carry_lt_tonnes: null, carry_spot_tonnes: null,
    plan_revenue_ty: null };

  const rowOf = (u: string): YearPlanRow => plans[u] ?? EMPTY;

  /** Sửa 1 ô trong nháp (chưa gọi API) — lưu khi rời ô. */
  const setCell = (u: string, key: keyof YearPlanRow, v: number | null) =>
    setPlans((p) => ({ ...p, [u]: { ...rowOf(u), [key]: v } }));

  const save = async (u: string) => {
    const r = rowOf(u);
    setSavingUnit(u);
    try {
      await saveYearPlan(role, year, u, r);
      message.success(`Đã lưu kế hoạch ${year} — ${u}`);
    } catch (e) {
      message.error((e as Error).message);
      load(); // hỏng thì nạp lại số thật
    } finally {
      setSavingUnit(null);
    }
  };

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
                      <td key={key} onBlur={() => canEditField(key) && save(u)}>
                        {numInput(r[key], (v) => setCell(u, key, v), !canEditField(key))}
                      </td>
                    ))}
                  </tr>
                );
              })}
              {units.length === 0 && !loading && (
                <tr><td colSpan={PLAN_FIELDS.length + 2}
                  style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                  Chưa có đơn vị nào.
                </td></tr>
              )}
              {units.length > 1 && (
                <tr style={{ fontWeight: 600, background: "rgba(125,125,125,.08)" }}>
                  <td />
                  <td>Tổng cộng</td>
                  {PLAN_FIELDS.map(({ key }) => <td key={key} className="r">{fmtNum(total(key), 3)}</td>)}
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Spin>
    </div>
  );
}
