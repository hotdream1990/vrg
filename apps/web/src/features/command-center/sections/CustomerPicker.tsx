/* Ô CHỌN KHÁCH HÀNG dùng chung — gõ để TÌM Ở SERVER, chọn 1 hoặc NHIỀU khách.

   Vì sao không đổ sẵn danh mục ra <select>: danh mục khách là RIÊNG của từng đơn vị, tổng số
   khách tăng theo số đơn vị nên tải hết về máy sẽ ngày càng nặng. Server cũng đã ép phạm vi đơn
   vị theo tài khoản (`cap_or_member_scope`), nên kết quả tìm luôn nằm trong quyền của người dùng.

   Nhãn LUÔN kèm tên đơn vị sở hữu khi đang xem nhiều đơn vị: các đơn vị hay có khách trùng/gần
   trùng tên ("SINTEX CHEMICAL CORP." của Đồng Nai ≠ "SINTEX CHEMICAL CORPORATION" của Dầu Tiếng)
   — thiếu tên đơn vị là chọn nhầm khách rồi tưởng bộ lọc hỏng. */

import { Select } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";

import { type Customer, searchCustomers } from "../../../lib/sales-contract-client";

/** Số kết quả tối đa mỗi lần tìm — đủ để chọn nhanh, không kéo cả danh mục về. */
const LIMIT = 50;
const DEBOUNCE_MS = 300;

type Opt = {
  value: number;
  label: string;    // nhãn đầy đủ (tên + mã + đơn vị) — dùng khi cần một chuỗi mô tả đủ ý
  short: string;    // nhãn NGẮN hiển thị trên thẻ đã chọn (ô lọc hẹp, nhãn dài sẽ bị gộp hết)
  name: string;
  company: string;
  inactive: boolean;
};

type Props = {
  /** Các id đang chọn (chế độ 1 khách: mảng rỗng hoặc 1 phần tử). */
  value: number[];
  onChange: (ids: number[]) => void;
  /** Chỉ tìm trong 1 đơn vị (form hợp đồng, hoặc khi bộ lọc đã chọn đơn vị). */
  company?: string;
  multiple?: boolean;
  placeholder?: string;
  disabled?: boolean;
  /** Cho chọn cả khách đã ẩn (mặc định chỉ khách đang dùng). */
  includeInactive?: boolean;
  width?: number | string;
};

const toOpt = (c: Customer): Opt => ({
  value: c.id as number,
  // Nhãn phẳng (không phải JSX) để chỗ nào cũng đọc được, kèm đơn vị sở hữu cho khỏi nhầm khách.
  label: `${c.name}${c.code ? ` (${c.code})` : ""} — ${c.company}${c.is_active ? "" : " · đã ẩn"}`,
  short: c.name,
  name: c.name,
  company: c.company,
  inactive: !c.is_active,
});

export default function CustomerPicker({
  value, onChange, company, multiple = false, placeholder = "Tất cả khách hàng",
  disabled, includeInactive = false, width = 260,
}: Props) {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Opt[]>([]);
  const [picked, setPicked] = useState<Opt[]>([]);   // nhãn của id đang chọn (giữ khi đổi từ khoá)
  const [loading, setLoading] = useState(false);
  const asked = useRef<Set<number>>(new Set());      // id đã hỏi server — chặn hỏi lại vô hạn

  // Gõ tới đâu tìm tới đó (chờ 300ms cho hết nhịp gõ). Đổi đơn vị thì tìm lại từ đầu.
  useEffect(() => {
    let alive = true;
    setLoading(true);
    const timer = setTimeout(() => {
      searchCustomers({ q, company, limit: LIMIT, includeInactive })
        .then((rows) => { if (alive) setFound(rows.map(toOpt)); })
        .catch(() => { if (alive) setFound([]); })
        .finally(() => { if (alive) setLoading(false); });
    }, q ? DEBOUNCE_MS : 0);
    return () => { alive = false; clearTimeout(timer); };
  }, [q, company, includeInactive]);

  const known = useMemo(() => {
    const m = new Map<number, Opt>();
    [...found, ...picked].forEach((o) => m.set(o.value, o));
    return m;
  }, [found, picked]);

  // Id đang chọn mà chưa biết tên (mở lại màn có sẵn bộ lọc, hoặc khách nằm ngoài trang kết quả)
  // → hỏi riêng theo id, kể cả khách đã ẩn, để thẻ hiện TÊN chứ không phải con số.
  useEffect(() => {
    const missing = value.filter((id) => !known.has(id) && !asked.current.has(id));
    if (!missing.length) return;
    missing.forEach((id) => asked.current.add(id));
    searchCustomers({ ids: missing, includeInactive: true })
      .then((rows) => setPicked((prev) => [...prev, ...rows.map(toOpt)]))
      // Gọi hỏng (mạng chập chờn) thì BỎ đánh dấu đã hỏi để lần sau hỏi lại — giữ nguyên là thẻ
      // đã chọn hiện con số id trần suốt phiên, đúng thứ nhập nhằng mà ô này sinh ra để tránh.
      .catch(() => missing.forEach((id) => asked.current.delete(id)));
  }, [value, known]);

  const options = useMemo(() => {
    const chosen = value.map((id) => known.get(id)).filter(Boolean) as Opt[];
    const m = new Map<number, Opt>();
    [...chosen, ...found].forEach((o) => m.set(o.value, o));
    return [...m.values()];
  }, [found, known, value]);

  const truncated = found.length >= LIMIT;

  return (
    <Select
      mode={multiple ? "multiple" : undefined}
      allowClear
      // Thẻ đã chọn hiện TÊN NGẮN (`short`): nhãn đầy đủ kèm đơn vị dài quá khổ ô lọc, antd gộp
      // hết thành "+ 2 …" và người dùng không thấy mình đang lọc theo khách nào.
      optionLabelProp="short"
      // Luôn hiện 1 thẻ + "+N": để antd tự co ("responsive") thì ô lọc hẹp không đủ chỗ cho thẻ
      // nào, người dùng chỉ thấy "+ 2 …" — không biết mình đang lọc theo khách nào.
      maxTagCount={multiple ? 1 : undefined}
      maxTagTextLength={18}
      style={{ minWidth: width }}
      placeholder={placeholder}
      disabled={disabled}
      loading={loading}
      // `filterOption: false` — server đã lọc rồi, để antd lọc lại lần nữa sẽ giấu mất kết quả
      // khớp theo mã / mã số thuế (những thứ không nằm trong nhãn hiển thị).
      showSearch={{ searchValue: q, onSearch: setQ, filterOption: false }}
      onBlur={() => setQ("")}
      value={multiple ? value : (value[0] ?? undefined)}
      onChange={(v) => {
        setQ("");
        onChange(v == null ? [] : (Array.isArray(v) ? (v as number[]) : [v as number]));
      }}
      options={options}
      optionRender={(o) => {
        const opt = o.data as Opt;
        return (
          <div>
            <div>{opt.name}</div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>
              {opt.company}{opt.inactive ? " · đã ẩn" : ""}
            </div>
          </div>
        );
      }}
      notFoundContent={loading ? "Đang tìm…" : "Không có khách hàng khớp từ khoá."}
      popupRender={(menu) => (
        <>
          {menu}
          {truncated && (
            <div style={{ padding: "6px 12px", fontSize: 11, color: "var(--muted)" }}>
              Chỉ hiện {LIMIT} kết quả đầu — gõ thêm để tìm đúng khách.
            </div>
          )}
        </>
      )}
    />
  );
}
