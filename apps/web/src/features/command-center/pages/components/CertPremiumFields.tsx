import NumInput from "../../sections/NumInput";

export type CertPremium = {
  certs: string[];
  premium: number | null;
  premium_ccy: string | null;
};

type Props = {
  value: CertPremium;
  /** Danh mục chứng chỉ + loại tiền lấy từ `meta` của hợp đồng (PEFC · EUDR · VRG GREEN). */
  certs: string[];
  currencies: string[];
  readOnly?: boolean;
  onChange: (patch: Partial<CertPremium>) => void;
};

/** Khoảng premium hay gặp (USD/tấn) — CHỈ để nhắc, không chặn: giá thoả thuận nằm ngoài là chuyện
 *  bình thường, chặn cứng là cản nghiệp vụ (cùng nguyên tắc với bộ cảnh báo biên nhập liệu). */
const USD_HINT = "thường 10–120 USD/tấn";

/**
 * Khối **HÀNG CÓ CHỨNG CHỈ** — dùng CHUNG cho form hợp đồng gốc (HĐNT/HĐDH) và hợp đồng bán.
 *
 * Chọn được nhiều chứng chỉ; ô premium **để trống** nếu hợp đồng không có khoản cộng thêm. Loại
 * tiền chọn USD hay VNĐ, số tiền tự nhập (yêu cầu 26/08/2026).
 */
export default function CertPremiumFields({ value, certs, currencies, readOnly, onChange }: Props) {
  const picked = new Set(value.certs ?? []);
  const ccy = value.premium_ccy ?? "USD";

  const toggle = (c: string) => {
    const next = new Set(picked);
    if (next.has(c)) next.delete(c); else next.add(c);
    onChange({ certs: certs.filter((x) => next.has(x)) });   // giữ thứ tự danh mục
  };

  return (
    <div style={{ marginTop: 12 }}>
      <h4 style={{ margin: "0 0 6px" }}>Hàng có chứng chỉ</h4>
      <div className="card" style={{ padding: 12, display: "flex", flexWrap: "wrap",
        gap: 14, alignItems: "flex-end" }}>
        <label className="form-field" style={{ flex: "1 1 320px" }}>
          <span>Chứng chỉ (chọn nhiều được)</span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 14, height: 34,
            alignItems: "center" }}>
            {certs.map((c) => (
              <label key={c} style={{ display: "flex", alignItems: "center", gap: 6,
                cursor: readOnly ? "default" : "pointer" }}>
                <input type="checkbox" checked={picked.has(c)} disabled={readOnly}
                  onChange={() => toggle(c)} />
                {c}
              </label>
            ))}
          </div>
        </label>
        <label className="form-field" style={{ flex: "0 1 190px" }}>
          <span>Premium cộng thêm</span>
          <NumInput value={value.premium} readOnly={readOnly}
            placeholder="để trống nếu không có"
            className="blt-date-input r"
            onChange={(v) => onChange({
              premium: v,
              // Bỏ trống premium thì loại tiền cũng hết nghĩa — để lại là bản ghi mang một loại
              // tiền không gắn với số nào (server cũng xoá, hai tầng phải khớp).
              premium_ccy: v == null ? null : (value.premium_ccy ?? "USD"),
            })} />
        </label>
        <label className="form-field" style={{ flex: "0 1 110px" }}>
          <span>Loại tiền</span>
          <select className="blt-date-input" value={ccy} disabled={readOnly || value.premium == null}
            onChange={(e) => onChange({ premium_ccy: e.target.value })}>
            {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
      </div>
      <div className="form-note" style={{ fontSize: 11.5, marginTop: 6 }}>
        Chọn chứng chỉ của lô hàng, và <b>Premium</b> là khoản khách trả thêm cho hàng có chứng chỉ
        ({USD_HINT}, hoặc nhập bằng VNĐ). <b>Không có premium thì để trống ô tiền.</b> Premium là số
        ghi nhận riêng — <b>không tự cộng vào đơn giá</b> ở phần chi tiết bên trên.
      </div>
    </div>
  );
}
