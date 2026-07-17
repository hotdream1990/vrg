/* Báo cáo tuần đơn vị (thu mua · tiêu thụ–tồn kho).
   - NHẬP LIỆU (đơn vị thành viên & chuyên viên GIỐNG NHAU): danh sách theo tuần (timeline) + modal nhập.
   - TỔNG HỢP (chuyên viên/admin): lưới toàn đơn vị theo mỗi tuần. */

import { ReloadOutlined, SettingOutlined } from "@ant-design/icons";
import { Button, Segmented, Select, Spin, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import { todayISO } from "../../../lib/date";
import { type WeekData, fetchWeek } from "../../../lib/unit-weekly-client";
import { KIND_LABEL, type Kind } from "../../../lib/unit-weekly-fields";
import { mondayOf, recentWeeks, weekLabel } from "../../../lib/week";
import UnitWeeklyEditModal from "./UnitWeeklyEditModal";
import UnitWeeklyOverview from "./UnitWeeklyOverview";
import UnitWeeklyPlanModal from "./UnitWeeklyPlanModal";
import UnitWeeklyTimeline from "./UnitWeeklyTimeline";
import "../../bulletin/bulletin.css";

const KIND_OPTS = [
  { label: KIND_LABEL.purchase, value: "purchase" },
  { label: KIND_LABEL.consumption, value: "consumption" },
];
const VIEW_OPTS = [
  { label: "Danh sách theo tuần", value: "list" },
  { label: "Tổng hợp toàn đơn vị", value: "overview" },
];

export default function UnitWeeklyPage() {
  const { user } = useAuth();
  const isMember = user?.role === "member";
  const isAdmin = user?.role === "admin";
  const role: "member" | "hq" = isMember ? "member" : "hq";

  const [kind, setKind] = useState<Kind>("purchase");
  const [view, setView] = useState<"list" | "overview">(isMember ? "list" : "overview");
  const [refreshKey, setRefreshKey] = useState(0);
  const [edit, setEdit] = useState<{ week: string; company: string } | null>(null);
  const [planOpen, setPlanOpen] = useState(false);

  // Tổng hợp (chỉ HQ): lưới toàn đơn vị theo 1 tuần.
  const [ovWeek, setOvWeek] = useState(mondayOf(todayISO()));
  const [ov, setOv] = useState<WeekData | null>(null);
  const [ovLoading, setOvLoading] = useState(false);

  const reload = () => setRefreshKey((k) => k + 1);

  const loadOv = useCallback(() => {
    if (isMember || view !== "overview") return;
    setOvLoading(true);
    fetchWeek(kind, ovWeek).then(setOv).catch((e) => message.error(e.message)).finally(() => setOvLoading(false));
  }, [isMember, view, kind, ovWeek]);
  useEffect(() => { loadOv(); }, [loadOv, refreshKey]);

  const ovCanEdit = useMemo(() => isAdmin || (ov ? ovWeek <= ov.today_week : false), [isAdmin, ov, ovWeek]);
  const weekOpts = recentWeeks(ov?.today_week ?? mondayOf(todayISO()), 20).map((w) => ({ value: w, label: weekLabel(w) }));

  return (
    <div className="main">
      <div className="page-title">
        <h2 style={{ margin: 0 }}>Báo cáo tiêu thụ - tồn kho</h2>
        <p style={{ margin: "4px 0 0" }}>
          Số liệu thu mua & tiêu thụ – tồn kho theo tuần, cập nhật realtime theo ngày.
        </p>
      </div>

      <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <Segmented value={kind} onChange={(v) => setKind(v as Kind)} options={KIND_OPTS} />
        {!isMember && <Segmented value={view} onChange={(v) => setView(v as "list" | "overview")} options={VIEW_OPTS} />}
        {!isMember && view === "overview" && (
          <>
            <Select value={ovWeek} onChange={setOvWeek} options={weekOpts} style={{ width: 220 }} />
            {kind === "purchase" && (
              <Button icon={<SettingOutlined />} onClick={() => setPlanOpen(true)}>Chỉ tiêu kế hoạch</Button>
            )}
            <Button icon={<ReloadOutlined />} onClick={loadOv}>Làm mới</Button>
          </>
        )}
      </div>

      {view === "list" || isMember ? (
        <UnitWeeklyTimeline
          kind={kind} role={role} isAdmin={isAdmin} refreshKey={refreshKey}
          onEdit={(week, company) => setEdit({ week, company })}
          onAdd={() => setEdit({ week: mondayOf(todayISO()), company: "" })}
        />
      ) : (
        <div className="card">
          <Spin spinning={ovLoading}>
            {ov && <UnitWeeklyOverview kind={kind} data={ov} canEdit={ovCanEdit} onEdit={(week, company) => setEdit({ week, company })} />}
          </Spin>
        </div>
      )}

      {edit && (
        <UnitWeeklyEditModal
          open kind={kind} role={role} isAdmin={isAdmin}
          initialWeek={edit.week} initialCompany={edit.company}
          todayWeek={mondayOf(todayISO())}
          onClose={() => setEdit(null)}
          onSaved={reload}
        />
      )}
      <UnitWeeklyPlanModal open={planOpen} year={Number(ovWeek.slice(0, 4))} onClose={() => setPlanOpen(false)} />
    </div>
  );
}
