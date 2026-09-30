/* Kết quả "Kiểm tra kết nối" SCADA: thành công → phiên bản + giờ máy SQL Server, số mới nhất (đã quy
   đổi) + giá trị thô từng tag để đối chiếu với màn SCADA của nhà máy; kết nối được nhưng có điểm cần
   kiểm tra (lệch múi giờ/đồng hồ, không có số gần đây…) → vàng + từng cảnh báo; lỗi → lý do. */

import { Alert, Descriptions, Modal, Result, Table } from "antd";

import type { ScadaTestResult } from "../../../../lib/smart-factory-client";
import { fmtNum, stampLocal, stampWithZone, withUnit } from "./smart-factory-format";

type Props = { name: string; result: ScadaTestResult; onClose: () => void };

/** Giá trị thô: giữ tối đa 3 số lẻ, không ép số lẻ cố định (thanh ghi là số nguyên). */
const rawNum = (v: number | null | undefined) =>
  (v == null ? "—" : v.toLocaleString("vi-VN", { maximumFractionDigits: 3 }));

function Success({ result }: { result: ScadaTestResult }) {
  const v = result.values ?? {};
  const raw = Object.entries(result.raw ?? {}).map(([tag, value]) => ({ tag, value }));
  const warnings = result.warnings ?? [];
  return (
    <>
      {/* detail chỉ nói thêm khi có điều cần lưu ý (chưa khai tag · 10 phút gần nhất không có số). */}
      <Result status={warnings.length ? "warning" : "success"}
        title={warnings.length ? "Kết nối được — có điểm cần kiểm tra" : "Kết nối thành công"}
        subTitle={result.detail !== "Kết nối thành công" ? result.detail : undefined}
        style={{ padding: "8px 0 16px" }} />
      {warnings.map((w, i) => (
        <Alert key={i} type="warning" showIcon className="sf-test-warn" title={w} />
      ))}
      <Descriptions size="small" bordered column={1} style={{ marginBottom: 14 }}
        items={[
          { key: "ver", label: "Phiên bản SQL Server",
            children: <span className="sf-code">{result.server_version || "—"}</span> },
          { key: "clock", label: "Giờ máy chủ SCADA", children: stampWithZone(result.server_time) },
          { key: "at", label: "Thời điểm số mới nhất", children: stampLocal(result.latest_at) },
          // Chỉ số chưa khai tag thì server không trả khoá → ẩn dòng (khác "có khai nhưng chưa có số").
          "energy_kwh" in v && { key: "kwh", label: "Điện năng", children: withUnit(fmtNum(v.energy_kwh, 3), "kWh") },
          "water_m3" in v && { key: "m3", label: "Nước", children: withUnit(fmtNum(v.water_m3, 3), "m³") },
          "bales" in v && { key: "bales", label: "Số bành", children: withUnit(fmtNum(v.bales, 0), "bành") },
        ].filter((x) => !!x)}
      />
      {raw.length > 0 && (
        <>
          <div className="sf-form-group">Giá trị thô từng tag</div>
          <Table
            rowKey="tag" size="small" pagination={false} dataSource={raw}
            columns={[
              { title: "Tag", dataIndex: "tag", key: "tag",
                render: (t: string) => <span className="sf-code">{t}</span> },
              { title: "Giá trị", dataIndex: "value", key: "value", align: "right",
                render: (x: number | null) => rawNum(x) },
            ]}
          />
        </>
      )}
    </>
  );
}

export default function ScadaTestResultModal({ name, result, onClose }: Props) {
  return (
    <Modal open width="min(640px, 94vw)" destroyOnHidden title={`Kiểm tra kết nối: ${name}`}
      onCancel={onClose} footer={null}>
      {result.ok ? <Success result={result} /> : (
        <Result status="error" title="Kết nối thất bại" subTitle={result.detail || "Không rõ lý do."}
          style={{ padding: "8px 0" }} />
      )}
    </Modal>
  );
}
