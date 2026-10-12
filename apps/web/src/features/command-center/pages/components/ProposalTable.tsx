/* Mục 5 — Đề xuất mua từ khách hàng - hàng VRG.
   Mỗi dòng: chủng loại (tự chọn) · khách hàng (tìm trong danh mục khách của hệ thống) · số lượng (tấn) ·
   đơn giá (đồng/tấn) · đơn giá (USD/tấn) · nguồn (tìm trong các công ty thành viên).
   Cùng một chủng loại có thể có nhiều dòng. Chỉ lưu trong phiếu (không mirror sang chuỗi giá). */

import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Select } from "antd";
import { useEffect, useMemo, useState } from "react";

import { listUnits } from "../../../../lib/member-unit-client";
import {
  type ProposalItem,
  type ProposalSection,
  emptyProposalItem,
} from "../../../../lib/market-quote-proposal";
import { foldFilterOption } from "../../../../lib/vn-fold";
import NumInput from "../../sections/NumInput";
import CustomerNameSelect from "./CustomerNameSelect";

type Props = {
  grades: string[];
  section: ProposalSection;
  readOnly?: boolean;
  /** Nhận HÀM cập nhật (không phải giá trị mới) để hai lần sửa liên tiếp không đè nhau. */
  onChange: (update: (s: ProposalSection) => ProposalSection) => void;
};

export default function ProposalTable({ grades, section, readOnly, onChange }: Props) {
  const [unitNames, setUnitNames] = useState<string[]>([]);
  useEffect(() => {
    listUnits(false).then((us) => setUnitNames(us.map((u) => u.name))).catch(() => setUnitNames([]));
  }, []);

  const gradeOptions = useMemo(() => grades.map((g) => ({ value: g, label: g })), [grades]);
  const unitOptions = useMemo(() => unitNames.map((n) => ({ value: n, label: n })), [unitNames]);

  const items = section.items ?? [];
  const patch = (i: number, p: Partial<ProposalItem>) =>
    onChange((s) => ({ ...s, items: s.items.map((it, k) => (k === i ? { ...it, ...p } : it)) }));
  const addRow = () => onChange((s) => ({ ...s, items: [...s.items, emptyProposalItem()] }));
  const removeRow = (i: number) => onChange((s) => ({ ...s, items: s.items.filter((_, k) => k !== i) }));

  return (
    <div className="card blt-section blt-editable" style={{ marginBottom: 16 }}>
      <div className="blt-section-header">
        <h3>5. Đề xuất mua từ khách hàng - Hàng VRG</h3>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          chủng loại · khách hàng · số lượng (tấn) · đơn giá (VNĐ/tấn, USD/tấn) · nguồn
        </span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Chủng loại</th>
            <th>Khách hàng</th>
            <th className="r">Số lượng (Tấn)</th>
            <th className="r">Đơn giá (Đồng/tấn)</th>
            <th className="r">Đơn giá (USD/Tấn)</th>
            <th>Nguồn</th>
            {!readOnly && <th style={{ width: 48 }} />}
          </tr>
        </thead>
        <tbody>
          {items.map((it, i) => (
            <tr key={i}>
              <td>
                <Select style={{ width: "100%", minWidth: 130 }} placeholder="Chọn chủng loại"
                  disabled={readOnly} allowClear value={it.grade || undefined} options={gradeOptions}
                  onChange={(v) => patch(i, { grade: v ?? "" })} />
              </td>
              <td>
                <CustomerNameSelect value={it.customer} disabled={readOnly}
                  onChange={(name) => patch(i, { customer: name })} />
              </td>
              <td className="r"><NumInput value={it.qty} readOnly={readOnly} onChange={(v) => patch(i, { qty: v })} /></td>
              <td className="r"><NumInput value={it.price_vnd} readOnly={readOnly} onChange={(v) => patch(i, { price_vnd: v })} /></td>
              <td className="r"><NumInput value={it.price_usd} readOnly={readOnly} onChange={(v) => patch(i, { price_usd: v })} /></td>
              <td>
                <Select style={{ width: "100%", minWidth: 190 }} placeholder="Chọn công ty thành viên"
                  disabled={readOnly} allowClear showSearch={{ filterOption: foldFilterOption }}
                  popupMatchSelectWidth={false} value={it.source || undefined} options={unitOptions}
                  onChange={(v) => patch(i, { source: v ?? "" })} />
              </td>
              {!readOnly && (
                <td className="r">
                  <button className="btn" title="Xoá dòng" aria-label={`Xoá dòng ${i + 1}`} onClick={() => removeRow(i)}>
                    <DeleteOutlined />
                  </button>
                </td>
              )}
            </tr>
          ))}
          {items.length === 0 && (
            <tr><td colSpan={readOnly ? 6 : 7} style={{ textAlign: "center", color: "var(--muted)", padding: 16 }}>
              Chưa có đề xuất nào{readOnly ? "." : " — bấm “Thêm dòng” bên dưới."}
            </td></tr>
          )}
        </tbody>
      </table>
      {!readOnly && (
        <div style={{ marginTop: 12 }}>
          <button className="btn" onClick={addRow}><PlusOutlined style={{ marginRight: 6 }} />Thêm dòng</button>
        </div>
      )}
      <label className="blt-date-label" style={{ display: "block", marginTop: 12 }}>Ghi chú / Thông tin
        <textarea className="blt-date-input" style={{ width: "100%", minHeight: 52, resize: "vertical" }}
          value={section.note} readOnly={readOnly} placeholder="Ghi chú đề xuất từ khách hàng…"
          onChange={(e) => onChange((s) => ({ ...s, note: e.target.value }))} />
      </label>
    </div>
  );
}
