/* Báo cáo tiêu thụ – tồn kho theo ngày (thu mua · tiêu thụ–tồn kho).
   - NHẬP LIỆU (đơn vị thành viên & chuyên viên GIỐNG NHAU): danh sách theo ngày (timeline) + modal nhập.
   - TỔNG HỢP (chuyên viên/admin): lưới toàn đơn vị theo mỗi ngày. */

import { ReloadOutlined, SettingOutlined } from "@ant-design/icons";
import { Button, Segmented, Spin, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import { todayISO } from "../../../lib/date";
import { type DayData, fetchDay } from "../../../lib/unit-daily-client";
import { KIND_LABEL, type Kind } from "../../../lib/unit-daily-fields";
import DateInput from "../sections/DateInput";
import UnitDailyEditModal from "./UnitDailyEditModal";
import UnitDailyOverview from "./UnitDailyOverview";
import UnitDailyPlanModal from "./UnitDailyPlanModal";
import UnitDailyTimeline from "./UnitDailyTimeline";
import "../../bulletin/bulletin.css";

const KIND_OPTS = [
  { label: KIND_LABEL.purchase, value: "purchase" },
  { label: KIND_LABEL.consumption, value: "consumption" },
];
const VIEW_OPTS = [
  { label: "Danh sách theo ngày", value: "list" },
  { label: "Tổng hợp toàn đơn vị", value: "overview" },
];

export default function UnitDailyPage() {
  const { user } = useAuth();
  const isMember = user?.role === "member";
  const isAdmin = user?.role === "admin";
  const role: "member" | "hq" = isMember ? "member" : "hq";

  const [kind, setKind] = useState<Kind>("purchase");
  const [view, setView] = useState<"list" | "overview">(isMember ? "list" : "overview");
  const [refreshKey, setRefreshKey] = useState(0);
  const [edit, setEdit] = useState<{ day: string; company: string } | null>(null);
  const [planOpen, setPlanOpen] = useState(false);

  // Tổng hợp (chỉ HQ): lưới toàn đơn vị theo 1 ngày.
  const [ovDay, setOvDay] = useState(todayISO());
  const [ov, setOv] = useState<DayData | null>(null);
  const [ovLoading, setOvLoading] = useState(false);

  const reload = () => setRefreshKey((k) => k + 1);

  const loadOv = useCallback(() => {
    if (isMember || view !== "overview") return;
    setOvLoading(true);
    fetchDay(kind, ovDay).then(setOv).catch((e) => message.error(e.message)).finally(() => setOvLoading(false));
  }, [isMember, view, kind, ovDay]);
  useEffect(() => { loadOv(); }, [loadOv, refreshKey]);

  const ovCanEdit = useMemo(() => isAdmin || (ov ? ovDay <= ov.today : false), [isAdmin, ov, ovDay]);

  return (
    <div className="main">
      <div className="page-title">
        <h2 style={{ margin: 0 }}>Báo cáo tiêu thụ - tồn kho</h2>
        <p style={{ margin: "4px 0 0" }}>
          Số liệu thu mua & tiêu thụ – tồn kho theo ngày, cập nhật realtime.
        </p>
      </div>

      <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <Segmented value={kind} onChange={(v) => setKind(v as Kind)} options={KIND_OPTS} />
        {!isMember && <Segmented value={view} onChange={(v) => setView(v as "list" | "overview")} options={VIEW_OPTS} />}
        {!isMember && view === "overview" && (
          <>
            <DateInput value={ovDay} onChange={setOvDay} noFuture style={{ width: 190 }} />
            {kind === "purchase" && (
              <Button icon={<SettingOutlined />} onClick={() => setPlanOpen(true)}>Chỉ tiêu kế hoạch</Button>
            )}
            <Button icon={<ReloadOutlined />} onClick={loadOv}>Làm mới</Button>
          </>
        )}
      </div>

      {view === "list" || isMember ? (
        <UnitDailyTimeline
          kind={kind} role={role} isAdmin={isAdmin} refreshKey={refreshKey}
          onEdit={(day, company) => setEdit({ day, company })}
          onAdd={() => setEdit({ day: todayISO(), company: "" })}
        />
      ) : (
        <div className="card">
          <Spin spinning={ovLoading}>
            {ov && <UnitDailyOverview kind={kind} data={ov} canEdit={ovCanEdit} onEdit={(day, company) => setEdit({ day, company })} />}
          </Spin>
        </div>
      )}

      {edit && (
        <UnitDailyEditModal
          open kind={kind} role={role} isAdmin={isAdmin}
          initialDay={edit.day} initialCompany={edit.company}
          today={todayISO()}
          onClose={() => setEdit(null)}
          onSaved={reload}
        />
      )}
      <UnitDailyPlanModal open={planOpen} year={Number(ovDay.slice(0, 4))} onClose={() => setPlanOpen(false)} />
    </div>
  );
}
