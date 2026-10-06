import type { ContractLine } from "../../../../lib/sales-contract-client";

type Props = {
  lines: ContractLine[];
  /** Nhãn nguồn từ server (`meta.sources`). */
  labels: Record<string, string>;
  /** Nguồn từng dòng theo ĐÚNG thứ tự `lines` ("" = chưa chọn). */
  value: string[];
  onChange: (next: string[]) => void;
};

const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });

/** Chọn NGUỒN TIÊU THỤ cho từng dòng chủng loại của một lần giao (hộp «Sửa nguồn», hộp «Hoàn
 *  thành hợp đồng»). Ô «Chọn nhanh» trên cùng điền một nguồn cho mọi dòng — phần lớn lần giao chỉ
 *  một nguồn, bắt chọn lại từng dòng là thừa thao tác. */
export default function LineSourcePicker({ lines, labels, value, onChange }: Props) {
  const options = Object.entries(labels ?? {});
  const at = (i: number) => value[i] ?? "";
  // Ô chọn nhanh hiện nguồn chung khi mọi dòng cùng một nguồn, còn lẫn nguồn thì để trống.
  const common = lines.length > 0 && lines.every((_, i) => at(i) === at(0)) ? at(0) : "";

  return (
    <div style={{ display: "grid", gap: 8 }}>
      {lines.length > 1 && (
        <label className="form-field">Chọn nhanh cho tất cả dòng
          <select className="blt-date-input" value={common}
            onChange={(e) => e.target.value && onChange(lines.map(() => e.target.value))}>
            <option value="">— chọn một nguồn cho mọi dòng —</option>
            {options.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      )}
      {lines.map((ln, i) => (
        <label key={i} className="form-field">
          <span>
            Dòng {i + 1}: <b>{ln.grade || "(chưa có chủng loại)"}</b>
            {ln.qty != null && <> · {t3(ln.qty)} tấn</>} — Nguồn tiêu thụ *
          </span>
          <select className="blt-date-input" value={at(i)}
            onChange={(e) => onChange(lines.map((_, k) => (k === i ? e.target.value : at(k))))}>
            <option value="">— chọn nguồn —</option>
            {options.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      ))}
    </div>
  );
}
