/* Ô CHỌN HỢP ĐỒNG MẸ (HĐNT/HĐDH) — gõ để TÌM Ở SERVER, giống <CustomerPicker>.

   Vì sao không đổ sẵn ra <select>: hồ sơ hợp đồng mẹ là của RIÊNG từng đơn vị và dài thêm mỗi
   năm. Server đã ép phạm vi đơn vị theo tài khoản nên kết quả tìm luôn nằm trong quyền. */

import { Select } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";

import { type MasterContract, searchMasterContracts } from "../../../lib/master-contract-client";

const LIMIT = 50;
const DEBOUNCE_MS = 300;

type Opt = {
  value: number;
  short: string;          // nhãn trên thẻ đã chọn = số hợp đồng
  label: string;
  customer: string;
  type: string;
  /** Đơn vị sở hữu hồ sơ — chỉ hiện khi đang xem NHIỀU đơn vị: hai đơn vị hoàn toàn có thể đánh
   *  trùng số hợp đồng, thiếu tên đơn vị là chọn nhầm hồ sơ mà không biết. */
  company: string;
};

type Props = {
  value: number | null;
  onChange: (id: number | null, master: MasterContract | null) => void;
  /** Chỉ tìm trong 1 đơn vị — hợp đồng mẹ của đơn vị khác không nối được (server cũng chặn). */
  company?: string;
  typeLabels: Record<string, string>;
  disabled?: boolean;
  /** Đặt lại chữ mờ trong ô (form nhập ≠ bộ lọc). */
  placeholder?: string;
  width?: number | string;
};

export default function MasterContractPicker({
  value, onChange, company, typeLabels, disabled,
  placeholder = "Gõ số hợp đồng mẹ (để trống nếu không có)", width = "100%",
}: Props) {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<MasterContract[]>([]);
  const [picked, setPicked] = useState<MasterContract[]>([]);  // nhãn của id đang chọn
  const [loading, setLoading] = useState(false);
  const asked = useRef<Set<number>>(new Set());

  useEffect(() => {
    let alive = true;
    setLoading(true);
    const timer = setTimeout(() => {
      searchMasterContracts({ q, company, limit: LIMIT })
        .then((rows) => { if (alive) setFound(rows); })
        .catch(() => { if (alive) setFound([]); })
        .finally(() => { if (alive) setLoading(false); });
    }, q ? DEBOUNCE_MS : 0);
    return () => { alive = false; clearTimeout(timer); };
  }, [q, company]);

  const known = useMemo(() => {
    const m = new Map<number, MasterContract>();
    [...found, ...picked].forEach((o) => m.set(o.id as number, o));
    return m;
  }, [found, picked]);

  // Mở lại form của một phụ lục cũ: hợp đồng mẹ đang chọn có thể không nằm trong 50 kết quả đầu
  // → hỏi riêng theo id, nếu không thẻ chỉ hiện con số id.
  useEffect(() => {
    if (!value || known.has(value) || asked.current.has(value)) return;
    asked.current.add(value);
    searchMasterContracts({ ids: [value] })
      .then((rows) => setPicked((prev) => [...prev, ...rows]))
      .catch(() => asked.current.delete(value));
  }, [value, known]);

  const options: Opt[] = useMemo(() => {
    const chosen = value ? [known.get(value)].filter(Boolean) as MasterContract[] : [];
    const m = new Map<number, MasterContract>();
    [...chosen, ...found].forEach((o) => m.set(o.id as number, o));
    return [...m.values()].map((o) => ({
      value: o.id as number,
      short: o.code,
      label: `${o.code} — ${typeLabels[o.master_type] ?? o.master_type}`,
      customer: o.customer_name ?? "—",
      type: typeLabels[o.master_type] ?? o.master_type,
      company: company ? "" : o.company,
    }));
  }, [found, known, value, typeLabels, company]);

  return (
    <Select
      allowClear
      optionLabelProp="short"
      style={{ minWidth: width }}
      placeholder={placeholder}
      disabled={disabled}
      loading={loading}
      // Server đã lọc rồi — để antd lọc lại sẽ giấu mất kết quả khớp theo ghi chú.
      showSearch={{ searchValue: q, onSearch: setQ, filterOption: false }}
      onBlur={() => setQ("")}
      value={value ?? undefined}
      onChange={(v) => {
        setQ("");
        const id = (v as number | undefined) ?? null;
        onChange(id, id ? known.get(id) ?? null : null);
      }}
      options={options}
      optionRender={(o) => {
        const opt = o.data as Opt;
        return (
          <div>
            <div>{opt.short}</div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>
              {opt.type} · {opt.customer}{opt.company ? ` · ${opt.company}` : ""}
            </div>
          </div>
        );
      }}
      notFoundContent={loading ? "Đang tìm…" : "Không có hợp đồng mẹ khớp từ khoá."}
    />
  );
}
