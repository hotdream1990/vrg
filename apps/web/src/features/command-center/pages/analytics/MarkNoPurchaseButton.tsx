/* Nút + hộp thoại ĐÁNH DẤU HÀNG LOẠT "không tổ chức thu mua" cho các ô còn trống. Chỉ admin thấy.
   Có đơn vị chỉ nhập ngày thật sự có thu mua, ngày không mua thì bỏ trắng thay vì tích ô — nhìn
   bảng theo dõi không phân biệt được "không tổ chức mua" với "quên nộp".

   Đơn vị và khoảng ngày CHỌN RIÊNG trong hộp thoại (bộ lọc đang xem chỉ là giá trị mặc định):
   phạm vi ghi dữ liệu phải do người bấm chỉ định rõ, không thừa hưởng ngầm từ màn hình. */

import { MinusCircleOutlined } from "@ant-design/icons";
import { Button, Modal, Spin, Table, message } from "antd";
import { useCallback, useEffect, useState } from "react";

import { dmy } from "../../../../lib/date";
import {
  type MarkNoPurchaseResult, type StatsFilters, markNoPurchase,
} from "../../../../lib/unit-analytics-client";
import { useAuth } from "../../../auth/AuthContext";
import DateInput from "../../sections/DateInput";
import { MultiSelect } from "./AnalyticsFilters";

type Props = {
  /** Bộ lọc đang xem — chỉ dùng làm giá trị MẶC ĐỊNH khi mở hộp thoại. */
  filters: StatsFilters;
  /** Danh sách đơn vị chọn được (đã lọc theo khu vực đang xem). */
  unitOptions: string[];
  onDone: () => void;
};

export default function MarkNoPurchaseButton({ filters, unitOptions, onDone }: Props) {
  const { user: me } = useAuth();
  const [open, setOpen] = useState(false);
  const [companies, setCompanies] = useState<string[]>([]);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [preview, setPreview] = useState<MarkNoPurchaseResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const ready = companies.length > 0 && !!from && !!to && from <= to;

  /** Xem trước: server chỉ đếm/liệt kê ô trống, KHÔNG ghi gì. Chạy lại mỗi lần đổi đơn vị/ngày. */
  const loadPreview = useCallback(() => {
    if (!open || !ready) { setPreview(null); return; }
    setLoading(true);
    markNoPurchase({ ...filters, from, to, companies, regions: [] }, false)
      .then(setPreview)
      .catch((e: Error) => { setPreview(null); message.error(e.message); })
      .finally(() => setLoading(false));
  }, [open, ready, from, to, companies]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { loadPreview(); }, [loadPreview]);

  if (me?.role !== "admin") return null;

  const start = () => {
    setCompanies(filters.companies.length ? filters.companies : []);
    setFrom(filters.from);
    setTo(filters.to);
    setPreview(null);
    setOpen(true);
  };

  const apply = () => {
    setSaving(true);
    markNoPurchase({ ...filters, from, to, companies, regions: [] }, true)
      .then((r) => {
        message.success(`Đã đánh dấu ${r.marked} ô "không tổ chức thu mua".`);
        setOpen(false);
        onDone();
      })
      .catch((e: Error) => message.error(e.message))
      .finally(() => setSaving(false));
  };

  return (
    <>
      <Button icon={<MinusCircleOutlined />} onClick={start}>Đánh dấu không tổ chức thu mua</Button>

      <Modal
        open={open} onCancel={() => setOpen(false)} onOk={apply}
        confirmLoading={saving} cancelText="Huỷ" width={640}
        okText={preview?.count ? `Đánh dấu ${preview.count} ô` : "Đánh dấu"}
        okButtonProps={{ disabled: !preview?.count || loading }}
        title="Đánh dấu không tổ chức thu mua cho các ô còn trống"
      >
        {/* Khoảng ngày Ở TRÊN, đơn vị ở dưới: danh sách đơn vị xổ xuống sẽ che mất hàng nằm ngay
            dưới nó — để ô ngày ở dưới thì phải đóng danh sách mới sửa được ngày. */}
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
          <DateInput value={from} onChange={setFrom} style={{ width: 160 }} />
          <span style={{ color: "var(--muted)" }}>→</span>
          <DateInput value={to} onChange={setTo} style={{ width: 160 }} />
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
          <MultiSelect placeholder="Chọn đơn vị" options={unitOptions} width={330}
                       value={companies} onChange={setCompanies} />
          <Button size="small" onClick={() => setCompanies(unitOptions)}>
            Chọn tất cả ({unitOptions.length})
          </Button>
        </div>

        <p className="form-note" style={{ fontSize: 12.5 }}>
          Việc này ghi hộ đơn vị rằng <b>ngày đó KHÔNG tổ chức thu mua</b> — chỉ dùng khi đã chắc
          chắn. Ngày <b>đã có số liệu vẫn giữ nguyên</b>, không bị ghi đè; ngày <b>sau hôm nay</b>{" "}
          bị bỏ qua. Muốn bỏ đánh dấu thì phải mở lại từng ngày để gỡ.
        </p>

        <Spin spinning={loading}>
          {!ready ? (
            <p style={{ color: "var(--muted)" }}>Chọn đơn vị và khoảng ngày để xem trước.</p>
          ) : (
            <>
              <p>
                Sẽ đánh dấu <b>{preview?.count ?? 0} ô trống</b> của{" "}
                <b>{preview?.units.length ?? 0} đơn vị</b>, từ <b>{dmy(from)}</b> đến <b>{dmy(to)}</b>.
              </p>
              <Table
                size="small" rowKey="company" pagination={false} scroll={{ y: 240 }}
                dataSource={preview?.units ?? []}
                locale={{ emptyText: "Các đơn vị đã chọn không còn ô trống nào trong khoảng này." }}
                columns={[
                  { title: "Đơn vị", dataIndex: "company" },
                  { title: "Số ngày", dataIndex: "days", align: "right", width: 90 },
                  { title: "Từ ngày", dataIndex: "first", width: 110, render: (d: string) => dmy(d) },
                  { title: "Đến ngày", dataIndex: "last", width: 110, render: (d: string) => dmy(d) },
                ]}
              />
            </>
          )}
        </Spin>
      </Modal>
    </>
  );
}
