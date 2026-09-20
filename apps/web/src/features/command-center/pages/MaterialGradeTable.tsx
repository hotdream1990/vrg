/* Bảng CHỦNG LOẠI của MỘT loại mủ nguyên liệu trên biểu Thu mua (chốt 20/09/2026) — mỗi dòng
   {chủng loại · sản lượng tấn quy khô}. Cùng khuôn với bảng tồn kho / thu mua thành phẩm.

   ĐƠN GIÁ KHÔNG nằm trong bảng: vẫn MỘT đơn giá cho cả loại mủ trong ngày (ô đơn giá đứng cạnh
   ô tổng), vì đơn giá đi vào kho "Giá mủ nguyên liệu" vốn không có chiều chủng loại.

   Chưa tách chủng loại (bảng rỗng) thì KHÔNG dựng bảng trống: 3 bảng trống làm form dài gấp đôi
   mà không thêm thông tin nào — chỉ hiện nút mời thêm dòng, ô tổng bên dưới vẫn gõ tay như cũ. */

import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Select } from "antd";

import { TONNES_DAILY } from "../../../lib/entry-bounds";
import { GRADES } from "../../../lib/unit-daily-consumption";
import { type MaterialGradeLine, emptyMaterialGradeLine } from "../../../lib/unit-daily-purchase";
import { numInput } from "./unit-daily-inputs";

type Props = {
  label: string;                                  // tên loại mủ — để nói rõ đang tách cho cái gì
  rows: MaterialGradeLine[];
  setRows: (next: MaterialGradeLine[]) => void;
  readOnly?: boolean;
};

const num = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);
const cell = { width: "100%" } as const;

export default function MaterialGradeTable({ label, rows, setRows, readOnly }: Props) {
  const patch = (i: number, p: Partial<MaterialGradeLine>) =>
    setRows(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));
  const addRow = () => setRows([...rows, emptyMaterialGradeLine()]);

  if (!rows.length) {
    if (readOnly) return null;   // ngày cũ chỉ có ô tổng — không bày thêm gì khi chỉ xem
    return (
      <>
        <button type="button" className="btn" style={{ fontSize: 12 }} onClick={addRow}>
          <PlusOutlined /> Tách chủng loại {label.toLowerCase()}
        </button>
        <div className="form-note" style={{ fontSize: 11.5, marginTop: 6 }}>
          Chưa tách chủng loại — cứ nhập thẳng <b>tổng sản lượng</b> ở ô bên dưới như trước.
          Bấm nút trên nếu muốn khai từng chủng loại; khi đó ô tổng <b>tự cộng</b> từ các dòng.
        </div>
      </>
    );
  }

  return (
    <>
      <div style={{ overflowX: "auto" }}>
        <table className="ud-sales ud-narrow">
          <thead><tr style={{ fontSize: 11.5, textAlign: "left", opacity: 0.7 }}>
            <th style={{ width: "60%" }}>Chủng loại</th>
            <th style={{ width: "33%" }} className="r">Sản lượng (tấn quy khô)</th>
            {!readOnly && <th style={{ width: "7%" }} />}
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>
                  <Select size="small" style={cell} value={r.grade || undefined} placeholder="Chủng loại"
                    disabled={readOnly} showSearch onChange={(v) => patch(i, { grade: v })}
                    options={GRADES.map((g) => ({ value: g, label: g }))} />
                </td>
                <td>{numInput(num(r.qty), (v) => patch(i, { qty: v }), readOnly, "small", TONNES_DAILY)}</td>
                {!readOnly && (
                  <td className="r">
                    <button type="button" className="btn" style={{ padding: "0 7px" }} title="Xoá dòng"
                      onClick={() => setRows(rows.filter((_, j) => j !== i))}><DeleteOutlined /></button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!readOnly && (
        <>
          <button type="button" className="btn" style={{ marginTop: 8, fontSize: 12 }}
            onClick={addRow}><PlusOutlined /> Thêm chủng loại</button>
          <div className="form-note" style={{ fontSize: 11.5, marginTop: 6 }}>
            Dòng <b>chưa điền sản lượng</b> thì không được tính vào ô tổng. Xoá hết dòng thì ô tổng
            mở lại cho <b>gõ tay</b>.
          </div>
        </>
      )}
    </>
  );
}
