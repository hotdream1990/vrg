import { useEffect, useState } from "react";

import { type SuggestItem, fetchFloorPoints, fetchFloorSuggest } from "../../../../lib/floor-suggest-client";

const vnum = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
const ACTION: Record<string, { t: string; c: string }> = {
  raise: { t: "NÂNG", c: "warn" }, hold: { t: "GIỮ", c: "" }, lower: { t: "HẠ", c: "danger" },
};

/** Gợi ý giá sàn (mô hình đa biến v2) so với giá sàn thực tế tại lần ban hành gần nhất. */
export default function ModelVsActualBlock() {
  const [items, setItems] = useState<SuggestItem[] | null>(null);
  const [meta, setMeta] = useState<{ as_of: string; basket: number | null } | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const pts = await fetchFloorPoints();
        if (!pts.length) { setItems([]); return; }
        const r = await fetchFloorSuggest(pts[0].as_of, "v2", true);
        setMeta({ as_of: r.as_of, basket: r.basket_change_pct });
        setItems(r.items);
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu");
      }
    })();
  }, []);

  const ready = !!items && items.length > 0;
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3 className={ready ? undefined : "title-demo"}>Gợi ý giá sàn: mô hình vs thực tế</h3>
          {meta && (
            <div className="sub">
              Mô hình đa biến (v2) · lần {meta.as_of}
              {meta.basket != null ? ` · rổ chỉ số ${meta.basket >= 0 ? "+" : ""}${meta.basket.toFixed(1)}% so lần trước` : ""}
            </div>
          )}
        </div>
        <span className={`chip ${ready ? "" : "demo"}`}>{ready ? "Dữ liệu thật" : "Chưa có dữ liệu"}</span>
      </div>
      {err ? <div className="scan-empty">{err}</div>
        : !items ? <div className="scan-empty">Đang tải…</div>
        : items.length === 0 ? <div className="scan-empty">Chưa có gợi ý (cần dữ liệu giá sàn + thị trường).</div>
        : (
          <div style={{ maxHeight: 300, overflow: "auto" }}>
            <table>
              <thead><tr><th>Chủng loại</th><th className="r">Thực tế</th><th className="r">Gợi ý</th><th className="r">Chênh</th><th>Đề xuất</th></tr></thead>
              <tbody>
                {items.map((it) => {
                  const a = it.action ? ACTION[it.action] : null;
                  return (
                    <tr key={it.grade}>
                      <td style={{ fontWeight: 500 }}>{it.grade}</td>
                      <td className="r">{it.actual != null ? vnum(it.actual) : "—"}</td>
                      <td className="r">{it.suggested != null ? vnum(it.suggested) : "—"}</td>
                      <td className="r" style={{ fontWeight: 600, color: it.diff == null ? "#5f6f67" : it.diff > 0 ? "#c0392b" : it.diff < 0 ? "#0b7a3b" : "#5f6f67" }}>
                        {it.diff == null ? "—" : `${it.diff >= 0 ? "+" : ""}${vnum(it.diff)}`}
                      </td>
                      <td>{a ? <span className={`chip ${a.c}`}>{a.t}</span> : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}
