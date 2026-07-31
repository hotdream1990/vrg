/* Thống kê hợp đồng — CHỈ ĐỌC. Liệt kê TẤT CẢ hợp đồng đã ký (bảng `unit_stock_contract`)
   đã từng nhập, KỂ CẢ hợp đồng đã giao (biến mất khỏi màn Báo cáo tồn kho theo ngày sau khi điền
   Ngày giao thực tế) — nơi tra cứu lại toàn bộ. */

import { HistoryOutlined } from "@ant-design/icons";
import { message } from "antd";
import { useEffect, useState } from "react";

import {
  type ContractHistoryFilters, type Role, type StockContract, fetchStockContractHistory,
} from "../../../lib/unit-daily-client";
import { useAuth } from "../../auth/AuthContext";
import ContractEditModal from "./ContractEditModal";
import StockContractHistoryFilters from "./StockContractHistoryFilters";
import StockContractHistoryTable from "./StockContractHistoryTable";

export default function StockContractHistoryPage() {
  const { user, canEditCap } = useAuth();
  const role: Role = user?.role === "member" ? "member" : "hq";
  const memberUnits = user?.member_units ?? [];
  const showCompany = role !== "member" || memberUnits.length > 1;
  // Đơn vị sửa được HĐ của mình; chuyên viên cần cap sửa `unit_daily`. Chỉ xem → không hiện nút Sửa.
  const canEdit = role === "member" || canEditCap("unit_daily");
  const [editing, setEditing] = useState<StockContract | null>(null);

  const [filters, setFilters] = useState<ContractHistoryFilters>({ status: "all" });
  const [units, setUnits] = useState<string[]>([]);
  const [regions, setRegions] = useState<string[]>([]);
  const [grades, setGrades] = useState<string[]>([]);
  const [rows, setRows] = useState<StockContract[]>([]);
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    fetchStockContractHistory(role, filters)
      .then((d) => {
        setUnits(d.units);
        setRegions(d.regions ?? []);
        setGrades(d.grades ?? []);
        // Endpoint của đơn vị thành viên không nhận tham số `company` (server đã tự giới hạn theo
        // đơn vị được gán) — lọc thêm ở CLIENT cho tài khoản gán nhiều đơn vị.
        setRows(role === "member" && filters.company
          ? d.contracts.filter((c) => c.company === filters.company)
          : d.contracts);
      })
      .catch((e) => message.error((e as Error).message || "Không tải được lịch sử hợp đồng."))
      .finally(() => setLoading(false));
  };

  // Bộ lọc chọn (đơn vị/trạng thái/ngày) gọi ngay; ô tìm kiếm gõ nhanh nên debounce nhẹ.
  useEffect(() => {
    const t = setTimeout(load, filters.q ? 350 : 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, role]);

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><HistoryOutlined style={{ marginRight: 8 }} />Thống kê hợp đồng</h2>
          <p>
            Thống kê toàn bộ hợp đồng đã ký đã từng nhập — <b>kể cả hợp đồng đã giao</b>, vốn không
            còn hiện trong màn Báo cáo tồn kho theo ngày sau khi điền Ngày giao thực tế.
            {canEdit
              ? <> Bấm <b>Sửa</b> để chỉnh hợp đồng (đơn giá, số lượng, ngày…) hoặc <b>mở lại</b> về “chưa giao”.</>
              : " Chỉ để tra cứu."}
          </p>
        </div>
      </div>

      <StockContractHistoryFilters
        units={units} regions={regions} grades={grades} showCompany={showCompany}
        value={filters} onChange={setFilters} onReload={load} loading={loading}
      />

      <div style={{ marginTop: 14 }}>
        <StockContractHistoryTable
          role={role} rows={rows} showCompany={showCompany} loading={loading}
          canEdit={canEdit} onEdit={setEditing}
        />
      </div>

      <ContractEditModal
        open={editing != null} role={role} contract={editing}
        onClose={() => setEditing(null)} onSaved={load}
      />
    </div>
  );
}
