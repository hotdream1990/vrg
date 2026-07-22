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
  setUnitFactory,
  setUnitLocale,
  setUnitPurchasePlan,
  setUnitRegion,
  updateUnit,
} from "../../../lib/member-unit-client";
import { useAuth } from "../../auth/AuthContext";
import DataSourceNote from "../sections/DataSourceNote";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import ManagedListTab, { type ListApi } from "./components/ManagedListTab";
import "../../bulletin/bulletin.css";

// Quốc gia + loại tiền hỗ trợ (đơn vị VRG ở VN, Lào, Campuchia). ≠ VND ⇒ cần nhập tỷ giá khi thu mua.
const LOCALES: { country: string; currency: string; label: string }[] = [
  { country: "VN", currency: "VND", label: "Việt Nam (VND)" },
  { country: "LA", currency: "LAK", label: "Lào (LAK)" },
  { country: "KH", currency: "KHR", label: "Campuchia (KHR)" },
];

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
  const { canEditCap } = useAuth();
  const canEdit = canEditCap("member_unit"); // mức Xem của mục này → khoá toàn bộ thao tác ghi
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

      <ReadOnlyNotice cap="member_unit" />
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
          extraCols={[
            {
              header: "Khu vực", width: 200,
              render: (u, run) => (
                <select className="blt-cell-input" style={{ minWidth: 160 }} value={u.region ?? ""} disabled={!canEdit}
                  onChange={(e) => run(() => setUnitRegion(u.name, e.target.value || null))}>
                  <option value="">— Chưa gán —</option>
                  {regions.filter((r) => r.is_active || r.name === u.region).map((r) => (
                    <option key={r.name} value={r.name}>{r.name}</option>
                  ))}
                </select>
              ),
            },
            {
              header: "Quốc gia / Tiền", width: 170,
              render: (u, run) => (
                <select className="blt-cell-input" style={{ minWidth: 150 }} value={u.country || "VN"} disabled={!canEdit}
                  onChange={(e) => {
                    const loc = LOCALES.find((l) => l.country === e.target.value) ?? LOCALES[0];
                    run(() => setUnitLocale(u.name, loc.country, loc.currency));
                  }}>
                  {LOCALES.map((l) => <option key={l.country} value={l.country}>{l.label}</option>)}
                </select>
              ),
            },
            {
              header: "Nhà máy", width: 150,
              render: (u, run) => (
                <select className="blt-cell-input" style={{ minWidth: 130 }} value={u.has_factory ? "1" : "0"} disabled={!canEdit}
                  onChange={(e) => run(() => setUnitFactory(u.name, e.target.value === "1"))}>
                  <option value="1">Có nhà máy</option>
                  <option value="0">Không có nhà máy</option>
                </select>
              ),
            },
            {
              header: "Kế hoạch thu mua", width: 140,
              render: (u, run) => (
                <label style={{ display: "flex", alignItems: "center", gap: 6, whiteSpace: "nowrap", cursor: canEdit ? "pointer" : "default" }}>
                  <input type="checkbox" checked={u.has_purchase_plan} disabled={!canEdit}
                    onChange={(e) => run(() => setUnitPurchasePlan(u.name, e.target.checked))} />
                  <span style={{ fontSize: 13, color: "var(--muted)" }}>Có giao KH</span>
                </label>
              ),
            },
          ]}
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
