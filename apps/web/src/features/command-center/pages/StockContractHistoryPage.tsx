/* Hợp đồng cũ (trước 30/07) — CHỈ XEM. Liệt kê TẤT CẢ hợp đồng đã ký nhập theo cách cũ (bảng
   `unit_stock_contract`), KỂ CẢ hợp đồng đã giao.

   Từ 02/08/2026 màn này KHÔNG còn sửa được: hợp đồng lập và sửa ở màn Quản lý hợp đồng
   (`sales_contract`). Dữ liệu cũ giữ nguyên để tra cứu, vào báo cáo sau khi chạy chuyển đổi. */

import { HistoryOutlined } from "@ant-design/icons";
import { message } from "antd";
import { useEffect, useState } from "react";

import {
  type ContractHistoryFilters, type Role, type StockContract, fetchStockContractHistory,
} from "../../../lib/unit-daily-client";
import { useAuth } from "../../auth/AuthContext";
import StockContractHistoryFilters from "./StockContractHistoryFilters";
import StockContractHistoryTable from "./StockContractHistoryTable";

export default function StockContractHistoryPage() {
  const { user, isUnitAccount } = useAuth();
  const role: Role = isUnitAccount ? "member" : "hq";
  const memberUnits = user?.member_units ?? [];

  const [filters, setFilters] = useState<ContractHistoryFilters>({ status: "all" });
  const [units, setUnits] = useState<string[]>([]);
  const [regions, setRegions] = useState<string[]>([]);
  const [grades, setGrades] = useState<string[]>([]);
  const [rows, setRows] = useState<StockContract[]>([]);
  const [loading, setLoading] = useState(false);
  // Cột "Đơn vị" phải hiện theo SỐ ĐƠN VỊ CÓ TRONG BẢNG, không theo số đơn vị được gán: tài khoản
  // một đơn vị nhưng đã nhận sáp nhập thì bảng có hợp đồng của cả hai, giấu cột là đọc nhầm chủ.
  const showCompany = role !== "member" || memberUnits.length > 1 || units.length > 1;

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
          <h2><HistoryOutlined style={{ marginRight: 8 }} />Hợp đồng cũ (trước 30/07)</h2>
          <p>
            Toàn bộ hợp đồng đã ký nhập theo cách cũ — <b>kể cả hợp đồng đã giao</b>. Màn này
            <b> chỉ để tra cứu</b>: hợp đồng nay lập và sửa ở màn <b>Quản lý hợp đồng</b>.
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
        />
      </div>
    </div>
  );
}
