/* Kế hoạch năm — số liệu lớn NHẬP 1 LẦN cho cả năm (không nhập hàng ngày), cập nhật khi có thay đổi:
   kế hoạch thu mua năm + tổng sản lượng đã ký hợp đồng dài hạn.
   Đơn vị thành viên: chỉ đơn vị của mình · Chuyên viên có quyền `unit_daily`: mọi đơn vị. */

import { ProfileOutlined } from "@ant-design/icons";
import { Select, Spin, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import { type Role, type YearPlanRow, fetchYearPlan, saveYearPlan } from "../../../lib/unit-daily-client";
import { fmtNum } from "../../../lib/unit-daily-fields";
import ExcelImportBar from "./components/ExcelImportBar";
import { numInput } from "./unit-daily-inputs";
import "../../bulletin/bulletin.css";

const YEARS = 6; // năm hiện tại + 2 năm trước/sau để chọn

export default function YearPlanPage() {
  const { user, canEditCap } = useAuth();
  const role: Role = user?.role === "member" ? "member" : "hq";
  // Chuyên viên chỉ được cấp mức Xem → khoá ô nhập (đơn vị thành viên không xét cap).
  const canEdit = role === "member" || canEditCap("unit_daily");
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

  const EMPTY: YearPlanRow = { plan_tonnes: null, plan_sales_spot_tonnes: null,
    signed_lt_tonnes: null, carry_lt_tonnes: null, carry_spot_tonnes: null };

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
        </div>
      </div>

      <div className="blt-toolbar" style={{ marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--muted)" }}>Năm:</span>
        <Select value={year} onChange={setYear} options={yearOpts} style={{ width: 140 }} />
        <span style={{ color: "var(--muted)", fontSize: 13 }}>{units.length} đơn vị</span>
        <ExcelImportBar kind="plan" role={role} label="Kế hoạch năm" onDone={load} />
      </div>

      <Spin spinning={loading}>
        <div className="card" style={{ padding: 0, overflow: "auto" }}>
          <table>
            <thead>
              <tr>
                <th style={{ width: 60 }}>#</th>
                <th>Đơn vị</th>
                <th className="r" style={{ width: 240 }}>Kế hoạch thu mua (tấn)</th>
                <th className="r" style={{ width: 240 }}>Kế hoạch tiêu thụ — HĐ chuyến (tấn)</th>
                <th className="r" style={{ width: 220 }}>HĐ dài hạn đã ký (tấn)</th>
                <th className="r" style={{ width: 220 }}>HĐ dài hạn 2025 chuyển sang (tấn)</th>
                <th className="r" style={{ width: 220 }}>HĐ chuyến 2025 chuyển sang (tấn)</th>
              </tr>
            </thead>
            <tbody>
              {units.map((u, i) => {
                const r = rowOf(u);
                return (
                  <tr key={u} style={{ opacity: savingUnit === u ? 0.6 : 1 }}>
                    <td>{i + 1}</td>
                    <td style={{ fontWeight: 500 }}>{u}</td>
                    <td onBlur={() => canEdit && save(u)}>
                      {numInput(r.plan_tonnes, (v) => setCell(u, "plan_tonnes", v), !canEdit)}
                    </td>
                    <td onBlur={() => canEdit && save(u)}>
                      {numInput(r.plan_sales_spot_tonnes, (v) => setCell(u, "plan_sales_spot_tonnes", v), !canEdit)}
                    </td>
                    <td onBlur={() => canEdit && save(u)}>
                      {numInput(r.signed_lt_tonnes, (v) => setCell(u, "signed_lt_tonnes", v), !canEdit)}
                    </td>
                    <td onBlur={() => canEdit && save(u)}>
                      {numInput(r.carry_lt_tonnes, (v) => setCell(u, "carry_lt_tonnes", v), !canEdit)}
                    </td>
                    <td onBlur={() => canEdit && save(u)}>
                      {numInput(r.carry_spot_tonnes, (v) => setCell(u, "carry_spot_tonnes", v), !canEdit)}
                    </td>
                  </tr>
                );
              })}
              {units.length === 0 && !loading && (
                <tr><td colSpan={7} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                  Chưa có đơn vị nào.
                </td></tr>
              )}
              {units.length > 1 && (
                <tr style={{ fontWeight: 600, background: "rgba(125,125,125,.08)" }}>
                  <td />
                  <td>Tổng cộng</td>
                  <td className="r">{fmtNum(total("plan_tonnes"), 3)}</td>
                  <td className="r">{fmtNum(total("plan_sales_spot_tonnes"), 3)}</td>
                  <td className="r">{fmtNum(total("signed_lt_tonnes"), 3)}</td>
                  <td className="r">{fmtNum(total("carry_lt_tonnes"), 3)}</td>
                  <td className="r">{fmtNum(total("carry_spot_tonnes"), 3)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Spin>
    </div>
  );
}
