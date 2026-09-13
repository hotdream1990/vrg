/* Dòng tóm tắt kết quả "Soát số liệu": không lệch (xanh) / còn N chỗ cần soát (vàng). */

import { CloseOutlined, SafetyCertificateOutlined, WarningOutlined } from "@ant-design/icons";

import type { WeeklyCheckResult } from "../../../../lib/weekly-report-client";

type Props = { result: WeeklyCheckResult | null; onClose: () => void };

export default function WeeklyCheckBanner({ result, onClose }: Props) {
  if (!result) return null;
  const close = (
    <button className="btn btn-sm wk-check-close" onClick={onClose} aria-label="Đóng"><CloseOutlined /></button>
  );
  if (result.count === 0) {
    return <div className="wk-check-banner wk-check-ok"><SafetyCertificateOutlined /> <span>{result.summary}</span>{close}</div>;
  }
  const remaining = Object.values(result.warnings).reduce((n, v) => n + v.length, 0);
  const text = remaining === result.count ? result.summary
    : `Còn ${remaining}/${result.count} chỗ chưa sửa — bấm "Soát số liệu" để soát lại.`;
  const where = result.warnings.latex_bands?.length ? " và dòng vàng ở bảng mủ nước III.3" : "";
  return (
    <div className="wk-ai-warn wk-check-banner">
      <WarningOutlined />
      <span>{text} Xem dòng vàng "Lệch dữ liệu hiện tại" dưới từng phần viết{where}. Số liệu đã về đủ thì
        sửa chữ theo bảng (hoặc chạy lại AI) trước khi xuất PDF.</span>
      {close}
    </div>
  );
}
