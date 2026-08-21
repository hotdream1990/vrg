import { CUP_PRICE_UNIT_SHORT, LATEX_PRICE_UNIT_SHORT } from "../../../../lib/purchase-price-unit";
import PurchaseCard, { type Kind } from "./PurchaseCard";

const WINDOW_DAYS = 30;   // cửa sổ hiển thị gần nhất cho dễ đọc

/** Hai loại mủ nguyên liệu đơn vị thành viên thu mua — cùng một khuôn card. */
const KINDS: Kind[] = [
  { key: "latex", title: "Thu mua mủ nước (nội địa)", unit: LATEX_PRICE_UNIT_SHORT, color: "#16AF67" },
  { key: "cup", title: "Thu mua mủ chén (nội địa)", unit: CUP_PRICE_UNIT_SHORT, color: "#a855f7" },
];

const from = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() - (days - 1));
  return d.toISOString().slice(0, 10);
};

/** Thu mua mủ nguyên liệu: mỗi loại mủ một card, xem được theo giá · khu vực · đơn vị. */
export default function RawMaterialBlock() {
  const start = from(WINDOW_DAYS);
  return (
    <div className="grid-2">
      {KINDS.map((k) => <PurchaseCard key={k.key} kind={k} from={start} />)}
    </div>
  );
}
