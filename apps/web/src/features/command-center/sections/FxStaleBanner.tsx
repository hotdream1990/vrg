import { WarningOutlined } from "@ant-design/icons";
import { Alert } from "antd";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { type FxStaleItem, describeStale, fetchFxHealth } from "../../../lib/fx-health-client";
import { useAuth } from "../../auth/AuthContext";

const SCAN_PAGE = "/quet-da-san";

/** Banner cảnh báo tỷ giá quá cũ — chỉ hiện cho tài khoản có quyền dữ liệu giá (`auto_data`).
 *
 * Server kiểm thẳng kho giá (không tin trạng thái crawler), nên bắt được cả kiểu hỏng "nguồn vẫn
 * báo OK nhưng thiếu cặp" (sự cố 03–13/09/2026). Gọi API 1 lần khi mở màn; đổi `reloadKey`
 * (vd sau khi bấm Quét) để kiểm lại. */
export default function FxStaleBanner({ reloadKey }: { reloadKey?: number }) {
  const { can } = useAuth();
  const allowed = can("auto_data");
  const { pathname } = useLocation();
  const [stale, setStale] = useState<FxStaleItem[]>([]);

  useEffect(() => {
    if (!allowed) return;
    let cancelled = false;
    fetchFxHealth()
      .then((r) => { if (!cancelled) setStale(r.stale); })
      .catch(() => { /* banner phụ — lỗi mạng không được làm vỡ màn chính */ });
    return () => { cancelled = true; };
  }, [allowed, reloadKey]);

  if (!allowed || stale.length === 0) return null;
  return (
    <Alert
      type="warning" showIcon icon={<WarningOutlined />}
      style={{ marginBottom: 14 }}
      title={
        <span>
          Tỷ giá {describeStale(stale)} — bản tin/báo cáo không quy đổi được USD.{" "}
          {pathname === SCAN_PAGE ? "Kiểm tra nguồn quét ở Nhật ký quét giá bên dưới." : (
            <Link to={SCAN_PAGE}>Kiểm tra nguồn quét.</Link>
          )}
        </span>
      }
    />
  );
}
