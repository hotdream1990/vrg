/* Mục 6 — Giá mủ tư nhân: mỗi dòng một đơn vị tư nhân, nhập MỘT giá hoặc KHOẢNG giá (Giá – Giá max).
   Cột "Giá thành SVR 3L" tự quy đổi theo công thức chuyên viên (lib/private-latex-cost.ts).
   Danh mục đơn vị dùng chung mọi phiếu: chuyên viên thêm được, chỉ quản trị viên xoá được.
   Giá theo ngày nằm trong phiếu nên xoá khỏi danh mục không mất giá ở các phiếu cũ. */

import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Popconfirm } from "antd";
import { useState } from "react";

import type { PrivatePrice, PrivateUnit } from "../../../../lib/market-quote-client";
import { formatViNumber } from "../../../../lib/number-format";
import {
  DEFAULT_SVR3L_PROCESSING_COST, PRIVATE_SVR3L_COEF, svr3lCost,
} from "../../../../lib/private-latex-cost";
import { LATEX_PRICE_UNIT } from "../../../../lib/purchase-price-unit";
import NumInput from "../../sections/NumInput";

type Field = keyof PrivatePrice;

type Props = {
  units: PrivateUnit[];
  prices: Record<string, PrivatePrice>;
  prevPrices?: Record<string, PrivatePrice>;
  readOnly?: boolean;
  /** Được thêm đơn vị vào danh mục (chuyên viên có quyền Sửa Báo giá). */
  canAdd?: boolean;
  /** Được xoá đơn vị khỏi danh mục (chỉ quản trị viên). */
  canDelete?: boolean;
  invalid: string[];
  /** Chi phí gia công chế biến SVR 3L (đồng/tấn) của phiếu; null = mặc định. */
  processingCost?: number | null;
  onProcessingCost: (v: number | null) => void;
  onPrice: (name: string, field: Field, v: number | null) => void;
  onAdd: (name: string) => Promise<void>;
  onDelete: (unit: PrivateUnit) => Promise<void>;
};

export default function PrivatePriceTable({
  units, prices, prevPrices, readOnly, canAdd, canDelete, invalid, processingCost, onProcessingCost,
  onPrice, onAdd, onDelete,
}: Props) {
  const cost = processingCost ?? DEFAULT_SVR3L_PROCESSING_COST;
  const coef = String(PRIVATE_SVR3L_COEF).replace(".", ",");
  const [name, setName] = useState("");
  const [adding, setAdding] = useState(false);
  const known = new Set(units.map((u) => u.name));
  // Phiếu cũ có thể còn giá của đơn vị đã bị xoá khỏi danh mục → vẫn hiện để không "mất" số.
  const orphans = Object.keys(prices).filter((n) => !known.has(n));
  const rows: { name: string; unit?: PrivateUnit }[] = [
    ...units.map((u) => ({ name: u.name, unit: u })),
    ...orphans.map((n) => ({ name: n })),
  ];

  const add = async () => {
    if (!name.trim() || adding) return;
    setAdding(true);
    // Lỗi (trùng tên…) đã được báo ở onAdd — giữ nguyên chữ vừa gõ để người dùng sửa lại.
    try { await onAdd(name); setName(""); } catch { /* đã báo */ } finally { setAdding(false); }
  };

  return (
    <div className="card blt-section blt-editable" style={{ marginBottom: 16 }}>
      <div className="blt-section-header">
        <h3>6. Giá mủ tư nhân</h3>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          {LATEX_PRICE_UNIT} · nhập 1 giá, hoặc Giá + Giá max nếu là khoảng giá
        </span>
      </div>
      <div className="private-cost-formula">
        <span>
          <b>Giá thành SVR 3L</b> (đồng/tấn) = Giá mủ × {coef} × 100.000 + Chi phí gia công chế biến
        </span>
        <label>
          Chi phí gia công chế biến SVR 3L:
          <span className="private-cost-input">
            <NumInput value={processingCost ?? null} readOnly={readOnly}
              placeholder={formatViNumber(DEFAULT_SVR3L_PROCESSING_COST)} onChange={onProcessingCost} />
          </span>
          đồng/tấn
        </label>
      </div>
      <table>
        <thead>
          <tr>
            <th>Đơn vị tư nhân</th>
            <th className="r">Giá</th>
            <th className="r">Giá max</th>
            <th className="r">Giá thành SVR 3L (đồng/tấn)</th>
            {canDelete && <th style={{ width: 48 }} />}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ name: n, unit }) => {
            const bad = invalid.includes(n);
            const lo = svr3lCost(prices[n]?.price, cost);
            const hi = prices[n]?.price_max != null && !bad ? svr3lCost(prices[n]?.price_max, cost) : null;
            const how = (v?: number | null) =>
              `${formatViNumber(v)} × ${coef} × 100.000 + ${formatViNumber(cost)} = ${formatViNumber(svr3lCost(v, cost))}`;
            return (
              <tr key={n}>
                <td style={{ fontWeight: 500 }}>
                  {n}
                  {!unit && <span style={{ marginLeft: 8, color: "var(--muted)", fontSize: 12 }}>(đã xoá khỏi danh mục)</span>}
                </td>
                <td className="r">
                  <NumInput value={prices[n]?.price ?? null} readOnly={readOnly}
                    prevValue={prevPrices?.[n]?.price} onChange={(v) => onPrice(n, "price", v)} />
                </td>
                <td className="r">
                  <NumInput value={prices[n]?.price_max ?? null} readOnly={readOnly}
                    className={bad ? "blt-cell-input num-invalid" : undefined}
                    title={bad ? "Giá max phải lớn hơn Giá" : undefined}
                    prevValue={prevPrices?.[n]?.price_max} onChange={(v) => onPrice(n, "price_max", v)} />
                </td>
                <td className="r private-cost-cell"
                  title={lo == null ? undefined : [how(prices[n]?.price), hi != null ? how(prices[n]?.price_max) : ""]
                    .filter(Boolean).join("\n")}>
                  {lo == null ? "—" : hi != null ? `${formatViNumber(lo)} – ${formatViNumber(hi)}` : formatViNumber(lo)}
                </td>
                {canDelete && (
                  <td className="r">
                    {unit && (
                      <Popconfirm title={`Xoá “${n}” khỏi danh mục?`}
                        description="Giá đã nhập ở các phiếu cũ vẫn giữ nguyên."
                        okText="Xoá" cancelText="Huỷ" okButtonProps={{ danger: true }}
                        onConfirm={() => onDelete(unit)}>
                        <button className="btn" title="Xoá khỏi danh mục" aria-label={`Xoá ${n}`}>
                          <DeleteOutlined />
                        </button>
                      </Popconfirm>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr><td colSpan={canDelete ? 5 : 4} style={{ textAlign: "center", color: "var(--muted)", padding: 16 }}>
              Chưa có đơn vị tư nhân nào{canAdd ? " — gõ tên bên dưới rồi bấm Thêm." : "."}
            </td></tr>
          )}
        </tbody>
      </table>
      {invalid.length > 0 && (
        <p className="form-note" style={{ margin: "8px 0 0" }}>
          Giá max phải lớn hơn Giá ({invalid.join(", ")}) — phiếu tạm chưa lưu cho tới khi sửa.
        </p>
      )}
      {canAdd && (
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <input className="blt-date-input" style={{ flex: 1, maxWidth: 420 }} value={name} maxLength={200}
            placeholder="Tên đơn vị tư nhân / khu vực mới, vd: Long Hòa, Phú Bình, Bến Súc"
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void add(); } }} />
          <button className="btn" onClick={() => void add()} disabled={!name.trim() || adding}>
            <PlusOutlined style={{ marginRight: 6 }} />Thêm đơn vị
          </button>
        </div>
      )}
    </div>
  );
}
