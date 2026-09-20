/* Khối THU MUA THÀNH PHẨM của biểu Thu mua — mua lại mủ ĐÃ CHẾ BIẾN, mỗi CHỦNG LOẠI một dòng với
   đơn giá riêng (khác hẳn mủ nguyên liệu: bên đó đơn giá là một ô chung cho cả loại mủ trong ngày).
   Tách khỏi `PurchaseForm` vì là khối tự quản: giữ luôn trạng thái lấy tỷ giá VCB cho các dòng USD. */

import { message } from "antd";
import { useState } from "react";

import { fetchVcbRate } from "../../../lib/market-quote-client";
import { HINT_DAILY_EVENT } from "../../../lib/unit-daily-entry-hints";
import { fmtNum } from "../../../lib/unit-daily-fields";
import { type FinishedLine, finishedTotals } from "../../../lib/unit-daily-purchase";
import FinishedPurchaseTable from "./FinishedPurchaseTable";
import { ENTRY_GRID, entryField, readOnlyBox, sectionHead } from "./unit-daily-inputs";

type Props = {
  rows: FinishedLine[];
  setRows: React.Dispatch<React.SetStateAction<FinishedLine[]>>;
  readOnly?: boolean;
  dimmed?: boolean;   // ngày đơn vị KHÔNG tổ chức thu mua → làm mờ cả khối
};

export default function FinishedPurchaseSection({ rows, setRows, readOnly, dimmed }: Props) {
  const [fxLoading, setFxLoading] = useState(false);
  const fin = finishedTotals(rows);

  /** Lấy tỷ giá VCB rồi điền cho MỌI dòng đang chọn USD — khỏi gõ lại từng dòng. */
  const fetchFx = async () => {
    setFxLoading(true);
    try {
      const r = await fetchVcbRate();
      const rate = r.mua_ck ?? r.ban ?? r.mua_tm;
      if (rate == null) throw new Error("VCB không có tỷ giá USD");
      setRows((list) => list.map((l) => ((l.ccy ?? "VND") === "USD" ? { ...l, fx: rate } : l)));
      message.success(`Đã điền tỷ giá USD/VND (VCB ${r.date}): ${fmtNum(rate, 0)} cho các dòng USD.`);
    } catch (e) {
      message.error((e as Error).message || "Không lấy được tỷ giá VCB — nhập tay giúp anh.");
    } finally {
      setFxLoading(false);
    }
  };

  return (
    <div style={{ opacity: dimmed ? 0.5 : 1, marginTop: 14 }}>
      {sectionHead("Thu mua thành phẩm", true, HINT_DAILY_EVENT)}
      <FinishedPurchaseTable rows={rows} setRows={setRows} readOnly={readOnly} />
      {!readOnly && (
        <div style={{ marginTop: 8 }}>
          <button type="button" className="btn" style={{ fontSize: 12 }} onClick={fetchFx} disabled={fxLoading}>
            {fxLoading ? "Đang lấy…" : "Lấy tỷ giá VCB cho các dòng USD"}
          </button>
        </div>
      )}
      <div className="form-note" style={{ fontSize: 11.5, marginTop: 8 }}>
        Mỗi chủng loại mua trong ngày là <b>một dòng riêng</b>. Đơn giá nhập theo loại tiền chọn ở
        cột <b>Tiền</b>: VNĐ thì <b>triệu đ/tấn</b>, USD thì <b>USD/tấn</b> — dòng nào chọn USD thì
        nhập <b>tỷ giá</b> ngay ở dòng đó{!readOnly && " (nút trên điền tỷ giá Vietcombank cho mọi dòng USD)"}.
      </div>

      {fin.qty > 0 && (
        <div style={{ ...ENTRY_GRID, marginTop: 10 }}>
          {entryField("Tổng SL thành phẩm", "tấn", readOnlyBox(fmtNum(fin.qty, 3), "tự tính"))}
          {entryField("Tổng giá trị", "triệu đồng", readOnlyBox(fmtNum(fin.valueVnd / 1_000_000, 1), "tự tính"))}
          {entryField("Đơn giá bình quân", "triệu đ/tấn", readOnlyBox(fmtNum(fin.avgPriceTrieu, 2), "tự tính"))}
        </div>
      )}
    </div>
  );
}
