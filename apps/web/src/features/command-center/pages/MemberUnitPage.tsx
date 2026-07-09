import { TeamOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";

import {
  type MemberRegion,
  addRegion,
  deleteRegion,
  listRegions,
  reorderRegions,
  updateRegion,
} from "../../../lib/member-region-client";
import {
  type MemberUnit,
  addUnit,
  deleteUnit,
  listUnits,
  reorderUnits,
  setUnitRegion,
  updateUnit,
} from "../../../lib/member-unit-client";
import { useAuth } from "../../auth/AuthContext";
import DataSourceNote from "../sections/DataSourceNote";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import ManagedListTab, { type ListApi } from "./components/ManagedListTab";
import "../../bulletin/bulletin.css";

// Api ổn định (khai báo ngoài component) — tránh ManagedListTab list lại mỗi lần render.
const unitApi: ListApi<MemberUnit> = {
  list: () => listUnits(),
  add: addUnit,
  rename: (n, nn) => updateUnit(n, { new_name: nn }),
  setActive: (n, a) => updateUnit(n, { is_active: a }),
  reorder: reorderUnits,
  remove: deleteUnit,
};
const regionApi: ListApi<MemberRegion> = {
  list: () => listRegions(),
  add: addRegion,
  rename: (n, nn) => updateRegion(n, { new_name: nn }),
  setActive: (n, a) => updateRegion(n, { is_active: a }),
  reorder: reorderRegions,
  remove: deleteRegion,
};

/** Quản lý số liệu → Đơn vị thành viên: 2 tab — Đơn vị (gán khu vực) + Khu vực (nhóm đơn vị). */
export default function MemberUnitPage() {
  const { canEdit } = useAuth();
  const [tab, setTab] = useState<"units" | "regions">("units");
  const [regions, setRegions] = useState<MemberRegion[]>([]);

  useEffect(() => { listRegions().then(setRegions).catch(() => {}); }, []);

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><TeamOutlined style={{ marginRight: 8 }} />Đơn vị thành viên</h2>
          <p>Đơn vị thành viên VRG và khu vực (nhóm đơn vị) dùng cho "Giá mủ nguyên liệu". Đổi tên giữ nguyên lịch sử giá đã nhập.</p>
        </div>
      </div>

      <ReadOnlyNotice />
      <DataSourceNote page="member-unit" />

      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <button className={`btn ${tab === "units" ? "btn-primary" : ""}`} onClick={() => setTab("units")}>Đơn vị</button>
        <button className={`btn ${tab === "regions" ? "btn-primary" : ""}`} onClick={() => setTab("regions")}>Khu vực</button>
      </div>

      {tab === "units" ? (
        <ManagedListTab<MemberUnit>
          api={unitApi} canEdit={canEdit}
          placeholder="Tên đơn vị mới (vd: Bình Long)" addLabel="Thêm đơn vị"
          countWord="đơn vị" nameHeader="Tên đơn vị"
          confirmDelete={(n) => `Xoá đơn vị "${n}" khỏi danh sách? (Giá đã nhập vẫn giữ trong kho)`}
          extraHeader="Khu vực"
          renderExtra={(u, run) => (
            <select className="blt-cell-input" style={{ minWidth: 160 }} value={u.region ?? ""} disabled={!canEdit}
              onChange={(e) => run(() => setUnitRegion(u.name, e.target.value || null))}>
              <option value="">— Chưa gán —</option>
              {regions.filter((r) => r.is_active || r.name === u.region).map((r) => (
                <option key={r.name} value={r.name}>{r.name}</option>
              ))}
            </select>
          )}
        />
      ) : (
        <ManagedListTab<MemberRegion>
          api={regionApi} canEdit={canEdit}
          placeholder="Tên khu vực mới (vd: Bình Dương)" addLabel="Thêm khu vực"
          countWord="khu vực" nameHeader="Tên khu vực"
          confirmDelete={(n) => `Xoá khu vực "${n}"? Các đơn vị đang thuộc khu vực này sẽ được gỡ gán.`}
          onItemsChange={setRegions}
        />
      )}
    </div>
  );
}
