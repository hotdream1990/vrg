import { SwapOutlined } from "@ant-design/icons";
import { useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import DataSourceNote from "../sections/DataSourceNote";
import DateRangeBar from "../sections/DateRangeBar";
import FxStaleBanner from "../sections/FxStaleBanner";
import PriceSheetGrid from "../sections/PriceSheetGrid";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import ScanNowButton from "../sections/ScanNowButton";
import "../../bulletin/bulletin.css";

/** Quản lý số liệu → Tỷ giá (USD/JPY·CNY·MYR·THB·VND theo ngày). */
export default function FxRatePage() {
  const { canEditCap } = useAuth();
  const canEdit = canEditCap("auto_data"); // mức Xem của mục này → khoá toàn bộ thao tác ghi
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><SwapOutlined style={{ marginRight: 8 }} />Tỷ giá (Exchange Rate)</h2>
          <p>Tỷ giá USD theo ngày (JPY · CNY · MYR · THB · VND) dùng quy đổi giá sàn — bấm ô để sửa.</p>
        </div>
      </div>

      <ReadOnlyNotice cap="auto_data" />
      <FxStaleBanner reloadKey={reloadKey} />
      <DataSourceNote page="fx" />
      <DateRangeBar from={from} to={to} onFrom={setFrom} onTo={setTo}>
        {canEdit && (
          <ScanNowButton source="fx" label="Quét tỷ giá" onDone={() => setReloadKey((k) => k + 1)} />
        )}
      </DateRangeBar>

      <PriceSheetGrid key={reloadKey} view="fx" dateFrom={from || undefined} dateTo={to || undefined} readOnly={!canEdit} />
    </div>
  );
}
