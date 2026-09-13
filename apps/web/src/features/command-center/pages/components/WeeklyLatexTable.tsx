/* III.3 Giá thu mua mủ nước (VNĐ/độ TSC): mỗi tuần 1 ô biên độ + mỗi cặp tuần 1 ô biến động.

   Luật override (khớp backend):
   - Hiển thị lấy report.latex_bands / latex_changes (máy chủ đã áp override; biến động tự tính theo
     biên độ đang hiển thị). Riêng lúc đang gõ (chưa lưu) thì hiện đúng chữ đang gõ.
   - KHÔNG khởi tạo override khi mở báo cáo — lưu cứng số tự tính thì giá sửa sau không vào báo cáo.
   - Người dùng sửa 1 ô → tạo list đúng độ dài, ô chưa sửa = null. Riêng báo cáo v1 (1 tuần, chưa có
     list, còn latex_prev/curr/change) thì list khởi tạo từ 3 số v1 — đó là số người dùng đã sửa tay
     thật, không phải số tự tính. Đã gửi list (kể cả toàn null)
     thì máy chủ chuyển chế độ v2 và bỏ 3 field v1 (latex_prev/curr/change).
   - "Dùng số tự tính" = gửi list toàn null (đúng độ dài).
   - Ô đang hiển thị (số đã lưu) khác số tự tính theo dữ liệu hiện tại → dòng vàng nêu số tự tính
     (so như backend `weekly_consistency_check.check_latex`: '495 – 559' = '495 - 559'; tuần chưa có
     số tự tính thì không báo; biến động chỉ báo khi biên độ đã khớp). */

import { UndoOutlined, WarningOutlined } from "@ant-design/icons";

import type { WeekCol, WeeklyNarrative } from "../../../../lib/weekly-report-client";

type Override = (string | null)[];
export type LatexPatch = Pick<WeeklyNarrative, "latex_override" | "latex_change_override">;

type Props = {
  weeks: WeekCol[];
  bands: (string | null)[];
  changes: (string | null)[];
  /** Số tự tính theo dữ liệu hiện tại (bất kể ghi đè). */
  autoBands: (string | null)[];
  autoChanges: (string | null)[];
  narrative: WeeklyNarrative;
  readOnly: boolean;
  onChange: (patch: LatexPatch) => void;
};

const nulls = (n: number): Override => Array.from({ length: n }, () => null);
const resize = (a: Override | null | undefined, n: number): Override =>
  Array.from({ length: n }, (_, i) => (Array.isArray(a) ? a[i] ?? null : null));
const hasValue = (a: Override | null | undefined) =>
  Array.isArray(a) && a.some((v) => typeof v === "string" && v.trim() !== "");
/** '515 - 540' / '515 – 540' → '515-540'; '540' → '540-540'; chữ lạ → null (như parse_band). */
const bandKey = (s: string | null | undefined) => {
  const nums = (s ?? "").match(/\d+/g) ?? [];
  return nums.length === 1 ? `${nums[0]}-${nums[0]}` : nums.length === 2 ? nums.join("-") : null;
};
const changeKey = (s: string | null | undefined) => (s ?? "").replace(/\s+/g, "").replace(/–/g, "-");

/** Các ô "đang dùng số đã lưu" khác số tự tính → ['T37: 495 - 564', …]. */
function staleCells(shorts: string[], bands: (string | null)[], changes: (string | null)[],
  autoBands: (string | null)[], autoChanges: (string | null)[]): string[] {
  const out = autoBands.flatMap((a, i) => (a && bandKey(bands[i]) !== bandKey(a) ? [`${shorts[i]}: ${a}`] : []));
  if (out.length) return out;   // biến động tính theo biên độ đang hiển thị → lệch theo, không nêu trùng
  return autoChanges.flatMap((a, i) =>
    (a && changeKey(changes[i]) !== changeKey(a) ? [`biến động ${shorts[i + 1]}/${shorts[i]}: ${a}`] : []));
}

export default function WeeklyLatexTable({
  weeks, bands, changes, autoBands, autoChanges, narrative: n, readOnly, onChange,
}: Props) {
  const nW = weeks.length;
  const nC = Math.max(0, nW - 1);
  const single = nW === 2;
  const bandOv = Array.isArray(n.latex_override) ? n.latex_override : null;
  const chOv = Array.isArray(n.latex_change_override) ? n.latex_change_override : null;
  const shorts = weeks.map((w) => w.short || `T${w.week_no}`);
  const hasV1 = single && !bandOv && !chOv && !!(n.latex_prev || n.latex_curr || n.latex_change);
  const stale = staleCells(shorts, bands, changes, autoBands, autoChanges);

  const setCell = (kind: "band" | "change", i: number, v: string) => {
    const b = resize(bandOv ?? (hasV1 ? [n.latex_prev ?? null, n.latex_curr ?? null] : null), nW);
    const c = resize(chOv ?? (hasV1 ? [n.latex_change ?? null] : null), nC);
    if (kind === "band") b[i] = v; else c[i] = v;
    onChange({ latex_override: b, latex_change_override: c });
  };
  const resetAuto = () => onChange({ latex_override: nulls(nW), latex_change_override: nulls(nC) });

  const cell = (kind: "band" | "change", i: number, shown: string | null, width: number) => {
    const ov = (kind === "band" ? bandOv : chOv)?.[i];
    const isOv = typeof ov === "string" && ov.trim() !== "";
    // Đang gõ (override là chuỗi) → hiện chữ đang gõ; ô trống thì số tự tính làm placeholder.
    const value = typeof ov === "string" ? ov : (shown ?? "");
    if (readOnly) return <td key={`${kind}${i}`} className="c">{shown ?? ""}</td>;
    return (
      <td key={`${kind}${i}`} className="c">
        <input className={`blt-cell-input wk-latex-input${isOv ? " wk-ov" : ""}`} style={{ width }}
          value={value} placeholder={shown ?? (kind === "band" ? "a - b" : "")}
          title={isOv ? "Đã sửa tay — bấm \"Dùng số tự tính\" để bỏ" : "Số tự tính — gõ để sửa (biên độ dạng a - b)"}
          onChange={(e) => setCell(kind, i, e.target.value)} />
      </td>
    );
  };

  return (
    <>
      <p className="sub">
        3. Giá thu mua mủ nước (VNĐ/độ TSC):{" "}
        <span className="db-badge">biên độ tự tính — sửa được</span>
        {!readOnly && (hasValue(bandOv) || hasValue(chOv) || hasV1) && (
          <button className="btn btn-sm wk-inline-btn" onClick={resetAuto}>
            <UndoOutlined /> Dùng số tự tính
          </button>
        )}
        {stale.length > 0 && (
          <span className="wk-ai-warn wk-inline">
            <WarningOutlined /> Đang dùng số đã lưu; số tự tính hiện tại: {stale.join(" · ")}
          </span>
        )}
      </p>
      <div className="wk-scroll">
        <table className="wk-table">
          <thead>
            <tr>
              <th>Sản phẩm</th>
              {weeks.map((w) => <th key={w.mon}>{w.label}</th>)}
              {weeks.slice(1).map((_, i) => (
                <th key={i}>{`Biến động (${shorts[i + 1]}/${shorts[i]})`}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="c">Mủ nước</td>
              {weeks.map((_, i) => cell("band", i, bands?.[i] ?? null, 120))}
              {weeks.slice(1).map((_, i) => cell("change", i, changes?.[i] ?? null, 100))}
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
