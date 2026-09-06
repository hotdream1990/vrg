/* Màn báo cáo theo ngày — DÙNG CHUNG cho 3 mục menu (mỗi mục cố định 1 loại biểu):
   Báo cáo thu mua · Báo cáo tiêu thụ · Báo cáo tồn kho (2 mục sau cùng biểu 'consumption', khác tab mở sẵn).
   - NHẬP LIỆU (đơn vị thành viên & chuyên viên GIỐNG NHAU): danh sách theo ngày (timeline) + modal nhập.
   - TỔNG HỢP (chuyên viên/admin): lưới toàn đơn vị theo mỗi ngày.
   Số liệu năm (kế hoạch thu mua, HĐ dài hạn đã ký) nhập ở trang riêng "Kế hoạch năm". */

import { ReloadOutlined } from "@ant-design/icons";
import { Button, Segmented, Spin, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import { todayISO } from "../../../lib/date";
import { type DayData, type Role, fetchDay } from "../../../lib/unit-daily-client";
import type { Kind } from "../../../lib/unit-daily-fields";
import DateInput from "../sections/DateInput";
import type { ImportKind } from "../../../lib/unit-daily-client";
import ExcelImportBar, { EXCEL_IMPORT_ENABLED } from "./components/ExcelImportBar";
import type { ConsumptionTab } from "./ConsumptionForm";
import UnitDailyEditModal from "./UnitDailyEditModal";
import UnitDailyOverview from "./UnitDailyOverview";
import UnitDailyTimeline from "./UnitDailyTimeline";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import { MultiSelect } from "./analytics/AnalyticsFilters";
import { filterDayByGrades, gradesOf } from "../../../lib/unit-daily-stock-filter";
import "../../bulletin/bulletin.css";

const VIEW_OPTS = [
  { label: "Danh sách theo ngày", value: "list" },
  { label: "Tổng hợp toàn đơn vị", value: "overview" },
];

type Props = {
  kind: Kind;
  title: string;
  subtitle: string;
  defaultTab?: ConsumptionTab;  // biểu 'consumption': mở sẵn tab Tiêu thụ hay Tồn kho
};

export default function UnitDailyPage({ kind, title, subtitle, defaultTab }: Props) {
  const { user, canEditCap, isUnitAccount, canEditUnitData } = useAuth();
  // `isMember` ở màn này = "tài khoản của đơn vị" (nhập liệu HOẶC lãnh đạo): cùng bố cục, cùng
  // bộ endpoint /api/member/*. Khác nhau ở quyền sửa — xem `mayEdit` bên dưới.
  const isMember = isUnitAccount;
  const isAdmin = user?.role === "admin";
  const role: Role = isMember ? "member" : "hq";

  const [view, setView] = useState<"list" | "overview">(isMember ? "list" : "overview");
  const [refreshKey, setRefreshKey] = useState(0);
  const [edit, setEdit] = useState<{ day: string; company: string } | null>(null);

  // `?ngay=&don-vi=` — bảng nhắc việc bấm thẳng vào ngày còn thiếu thì mở luôn phiếu của ngày đó.
  // Xoá tham số ngay sau khi mở: để lại thì bấm F5 hay quay lại trang là form tự bật lần nữa.
  const [params, setParams] = useSearchParams();
  useEffect(() => {
    const day = params.get("ngay");
    if (!day) return;
    setEdit({ day, company: params.get("don-vi") || "" });
    setParams({}, { replace: true });
  }, [params, setParams]);

  // Tổng hợp (chỉ HQ): lưới toàn đơn vị theo 1 ngày.
  const [ovDay, setOvDay] = useState(todayISO());
  const [ov, setOv] = useState<DayData | null>(null);
  const [ovGrades, setOvGrades] = useState<string[]>([]);   // lọc chủng loại cho lưới tồn kho
  const [ovLoading, setOvLoading] = useState(false);

  const reload = () => setRefreshKey((k) => k + 1);

  const loadOv = useCallback(() => {
    if (isMember || view !== "overview") return;
    setOvLoading(true);
    fetchDay(kind, ovDay).then(setOv).catch((e) => message.error(e.message)).finally(() => setOvLoading(false));
  }, [isMember, view, kind, ovDay]);
  useEffect(() => { loadOv(); }, [loadOv, refreshKey]);

  // Loại biểu để nhập Excel: Thu mua → purchase; Tiêu thụ → sales; Tồn kho → stock.
  const importKind: ImportKind = kind === "purchase" ? "purchase" : (defaultTab ?? "sales");

  // Chuyên viên chỉ được cấp mức Xem → luôn "Xem" dù ngày còn trong cửa sổ sửa.
  // Lãnh đạo đơn vị cũng rơi vào nhánh này: xem được đúng số liệu đơn vị mình, không sửa.
  const mayEdit = canEditUnitData || canEditCap("unit_daily");
  const showImport = mayEdit && EXCEL_IMPORT_ENABLED;
  // Danh mục chủng loại lấy từ CHÍNH số liệu đang xem — không cần gọi thêm API, và chỉ hiện những
  // chủng loại thật sự có tồn kho trong ngày đó.
  const ovGradeOpts = useMemo(() => gradesOf(ov), [ov]);
  // Lọc chủng loại chạy ở máy: dữ liệu ngày đã tải đủ, lọc lại ở server chỉ thêm một vòng chờ.
  const ovShown = useMemo(() => filterDayByGrades(ov, ovGrades), [ov, ovGrades]);

  const ovCanEdit = useMemo(
    () => mayEdit && (isAdmin || (ov ? ovDay <= ov.today : false)),
    [mayEdit, isAdmin, ov, ovDay],
  );

  return (
    <div className="main">
      <div className="page-title">
        <h2 style={{ margin: 0 }}>{title}</h2>
        <p style={{ margin: "4px 0 0" }}>{subtitle}</p>
      </div>

      <ReadOnlyNotice cap="unit_daily" />

      {/* Thanh công cụ chỉ dựng khi thật sự có nút — không thì để lại một card trống. */}
      {(!isMember || showImport) && (
        <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          {!isMember && (
            <Segmented value={view} onChange={(v) => setView(v as "list" | "overview")} options={VIEW_OPTS} />
          )}
          {showImport && <ExcelImportBar kind={importKind} role={role} label={title} onDone={reload} />}
        </div>
      )}

      {!isMember && view === "overview" && (
        <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <DateInput value={ovDay} onChange={setOvDay} noFuture style={{ width: 190 }} />
          {/* Lọc chủng loại chỉ có nghĩa với biểu TỒN KHO: khối 1 & khối 2 vốn khai theo từng
              chủng loại nên lọc được; biểu Thu mua khai theo loại nguyên liệu, không có bảng này. */}
          {kind === "consumption" && (
            <MultiSelect placeholder="Tất cả chủng loại" options={ovGradeOpts} width={230}
              value={ovGrades} onChange={setOvGrades} />
          )}
          <Button icon={<ReloadOutlined />} onClick={loadOv}>Làm mới</Button>
          {!!ovGrades.length && (
            <span className="form-note" style={{ fontSize: 11.5 }}>
              Cột tồn kho chỉ cộng {ovGrades.length} chủng loại đang chọn.
            </span>
          )}
        </div>
      )}

      {view === "list" || isMember ? (
        <UnitDailyTimeline
          kind={kind} role={role} isAdmin={isAdmin} canEdit={mayEdit} refreshKey={refreshKey}
          onEdit={(day, company) => setEdit({ day, company })}
          onAdd={() => setEdit({ day: todayISO(), company: "" })}
        />
      ) : (
        <div className="card">
          <Spin spinning={ovLoading}>
            {ovShown && <UnitDailyOverview kind={kind} data={ovShown} canEdit={ovCanEdit} onEdit={(day, company) => setEdit({ day, company })} />}
          </Spin>
        </div>
      )}

      {edit && (
        <UnitDailyEditModal
          open kind={kind} role={role} isAdmin={isAdmin} canEdit={mayEdit} defaultTab={defaultTab}
          initialDay={edit.day} initialCompany={edit.company}
          today={todayISO()}
          onClose={() => setEdit(null)}
          onSaved={reload}
        />
      )}
    </div>
  );
}
