import { useEffect, useState } from "react";

import { type PriceBoard, fetchBoard } from "../../../lib/api-client";

const EX_LABEL: Record<string, string> = {
  OSE: "OSE (TOCOM)",
  SHANGHAI: "SHFE (Thượng Hải)",
  SGX: "SGX (Singapore)",
  MRE: "MRB (Malaysia)",
};

const fmt = (v: number | null | undefined, d = 0) =>
  v == null ? "—" : v.toLocaleString("vi-VN", { maximumFractionDigits: d });

/** Bảng giá sàn dạng "thành phần" (giá nội tệ · tỷ giá · USD/T) + mục Tỷ giá — giống sheet Excel.
    Conversion tính ở backend (1 nguồn quy đổi). reloadKey đổi → nạp lại sau khi Quét/Nạp. */
export default function ExchangeBoard({ reloadKey = 0 }: { reloadKey?: number }) {
  const [board, setBoard] = useState<PriceBoard | null>(null);

  useEffect(() => {
    void fetchBoard()
      .then(setBoard)
      .catch(() => setBoard(null));
  }, [reloadKey]);

  if (!board || (board.exchanges.length === 0 && board.fx.length === 0)) return null;

  return (
    <div
      className="board-grid"
      style={{ display: "grid", gridTemplateColumns: "minmax(0,2.2fr) minmax(0,1fr)", gap: 16, marginBottom: 18 }}
    >
      <div className="card">
        <div className="card-head">
          <div>
            <h3>Giá sàn — thành phần</h3>
            <div className="sub">Giá nội tệ · Tỷ giá · USD/T (quy đổi theo sheet gốc VRG)</div>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Sàn</th>
              <th>Mặt hàng</th>
              <th style={{ textAlign: "right" }}>Giá nội tệ</th>
              <th>ĐVT gốc</th>
              <th style={{ textAlign: "right" }}>Tỷ giá</th>
              <th style={{ textAlign: "right" }}>USD/T</th>
              <th>Ngày</th>
            </tr>
          </thead>
          <tbody>
            {board.exchanges.map((e, i) => (
              <tr key={i}>
                <td>{EX_LABEL[e.exchange] ?? e.exchange}</td>
                <td style={{ fontWeight: 500 }}>{e.grade}</td>
                <td style={{ textAlign: "right" }}>{fmt(e.native_price, 3)}</td>
                <td>{e.native_unit}</td>
                <td style={{ textAlign: "right" }}>
                  {e.fx_rate != null ? `${fmt(e.fx_rate, 4)}` : "—"}
                  {e.fx_pair && <span style={{ color: "var(--muted)", fontSize: 11 }}> ({e.fx_pair})</span>}
                </td>
                <td style={{ textAlign: "right", fontWeight: 600 }}>{fmt(e.usd_tonne)}</td>
                <td>{e.as_of}</td>
              </tr>
            ))}
            {board.exchanges.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", color: "var(--muted)", padding: 16 }}>
                  Chưa có giá sàn — bấm “Quét giá ngay”.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <div className="card-head">
          <div>
            <h3>Tỷ giá (Exchange Rate)</h3>
            <div className="sub">1 USD = …</div>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Cặp</th>
              <th style={{ textAlign: "right" }}>Tỷ giá</th>
              <th>Ngày</th>
            </tr>
          </thead>
          <tbody>
            {board.fx.map((f, i) => (
              <tr key={i}>
                <td style={{ fontWeight: 500 }}>{f.pair}</td>
                <td style={{ textAlign: "right" }}>{fmt(f.rate, 4)}</td>
                <td>{f.as_of ?? "—"}</td>
              </tr>
            ))}
            {board.fx.length === 0 && (
              <tr>
                <td colSpan={3} style={{ textAlign: "center", color: "var(--muted)", padding: 16 }}>
                  Chưa có tỷ giá — bấm “Quét giá ngay”.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
