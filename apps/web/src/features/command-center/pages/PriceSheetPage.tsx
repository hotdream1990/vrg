import { TableOutlined } from "@ant-design/icons";
import { useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import DataSourceNote from "../sections/DataSourceNote";
import DateRangeBar from "../sections/DateRangeBar";
import PriceSheetGrid from "../sections/PriceSheetGrid";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import ScanNowButton from "../sections/ScanNowButton";
import "../../bulletin/bulletin.css";

/** Quản lý số liệu → Bảng tính giá các sàn (Native·Tỷ giá·USD/T theo ngày, giống file mẫu). */
export default function PriceSheetPage() {
  const { canEditCap } = useAuth();
  const canEdit = canEditCap("auto_data"); // mức Xem của mục này → khoá toàn bộ thao tác ghi
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><TableOutlined style={{ marginRight: 8 }} />Bảng tính giá các sàn</h2>
          <p>Giá nội tệ · Tỷ giá · USD/T theo ngày (OSE · SHANGHAI · SGX · MRB) — bấm ô để sửa, ghi đè kho giá.</p>
        </div>
      </div>

      <ReadOnlyNotice cap="auto_data" />
      <DataSourceNote page="price-sheet" />
      <DateRangeBar from={from} to={to} onFrom={setFrom} onTo={setTo}>
        {canEdit && (
          <ScanNowButton source="shfe,tocom,lgm,sgx" label="Quét các sàn" onDone={() => setReloadKey((k) => k + 1)} />
        )}
      </DateRangeBar>

      <PriceSheetGrid key={reloadKey} view="exchange" dateFrom={from || undefined} dateTo={to || undefined} readOnly={!canEdit} />
    </div>
  );
}
