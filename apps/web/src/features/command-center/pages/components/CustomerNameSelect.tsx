/* Ô chọn KHÁCH HÀNG theo TÊN — gõ để tìm Ở SERVER trong danh mục khách hàng của hệ thống.

   Chỉ tải khi mở danh sách (không bắn một loạt yêu cầu lúc mở phiếu có nhiều dòng) và chờ hết nhịp
   gõ. Lưu TÊN (không phải id) vì phiếu báo giá là bản ghi theo ngày: đổi/ẩn khách về sau thì phiếu
   cũ vẫn giữ nguyên tên đã chọn. */

import { Select } from "antd";
import { useEffect, useMemo, useState } from "react";

import { type CustomerOption, fetchCustomerOptions } from "../../../../lib/market-quote-proposal";

const DEBOUNCE_MS = 300;
/** Khớp giới hạn mặc định của server — đủ số kết quả này thì có thể còn khách chưa hiện. */
const SERVER_LIMIT = 50;

type Props = {
  value: string;
  onChange: (name: string) => void;
  disabled?: boolean;
};

export default function CustomerNameSelect({ value, onChange, disabled }: Props) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [found, setFound] = useState<CustomerOption[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setLoading(true);
    const timer = setTimeout(() => {
      fetchCustomerOptions(q)
        .then((rows) => { if (alive) setFound(rows); })
        .catch(() => { if (alive) setFound([]); })
        .finally(() => { if (alive) setLoading(false); });
    }, q ? DEBOUNCE_MS : 0);
    return () => { alive = false; clearTimeout(timer); };
  }, [open, q]);

  const options = useMemo(
    () => found.map((c) => ({ value: c.name, label: c.name, company: c.company, units: c.units })),
    [found],
  );

  return (
    <Select
      allowClear
      popupMatchSelectWidth={false}
      disabled={disabled}
      loading={loading}
      style={{ width: "100%", minWidth: 210 }}
      placeholder="Chọn khách hàng…"
      value={value || undefined}
      options={options}
      // `filterOption: false` — server đã lọc (kể cả khớp theo mã / mã số thuế, không nằm trong nhãn).
      showSearch={{ searchValue: q, onSearch: setQ, filterOption: false }}
      onOpenChange={(o) => { setOpen(o); if (!o) setQ(""); }}
      onChange={(v) => { setQ(""); onChange(v ?? ""); }}
      optionRender={(o) => {
        const d = o.data as (typeof options)[number];
        return (
          <div>
            <div>{d.label}</div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>
              {d.units > 1 ? `${d.units} đơn vị thành viên` : d.company}
            </div>
          </div>
        );
      }}
      notFoundContent={loading ? "Đang tìm…" : "Không có khách hàng khớp từ khoá."}
      popupRender={(menu) => (
        <>
          {menu}
          {found.length >= SERVER_LIMIT && (
            <div style={{ padding: "6px 12px", fontSize: 11, color: "var(--muted)" }}>
              Chỉ hiện {SERVER_LIMIT} kết quả đầu — gõ thêm để tìm đúng khách.
            </div>
          )}
        </>
      )}
    />
  );
}
