/* Định dạng số & quy tắc chữ dùng chung cho màn Báo cáo tuần (bám mẫu: chấm nghìn, phẩy thập phân). */

type N = number | null | undefined;

/** Số kiểu VN: chấm nghìn, phẩy thập phân. */
export function vn(x: N, dec: number): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "N/A";
  const s = Math.abs(x).toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  const v = s.replace(/,/g, " ").replace(/\./g, ",").replace(/ /g, ".");
  return x < 0 ? `-${v}` : v;
}

/** Có dấu +/- (bảng mẫu 35–36): "+35,4" · "-26,3" · "0" (khớp PDF). */
export function signed(x: N, dec: number, suffix = ""): string {
  if (x === null || x === undefined) return "";
  const r = Number(x.toFixed(dec));
  if (r === 0) return `0${suffix}`;
  return `${r > 0 ? "+" : "-"}${vn(Math.abs(x), dec)}${suffix}`;
}

/** Số lẻ theo độ lớn (chỉ số/tỷ giá): ≥ 10 → 2 số lẻ (DXY, WTI, USD/JPY), còn lại 4 (USD/CNY, USD/MYR). */
export const autoDec = (x: N) => (x !== null && x !== undefined && Math.abs(x) < 10 ? 4 : 2);

/** Số lẻ của giá nội tệ theo đơn vị (JPY/kg 1 · CNY/tấn 0 · US cent/kg 1). */
export const nativeDec = (unit: string | null) => (unit && /CNY/i.test(unit) ? 0 : 1);

/** 'YYYY-MM-DD' → 'dd/mm/yyyy' (hoặc 'dd/mm' khi short). Chuỗi khác giữ nguyên. */
export function viDate(s: string | null | undefined, short = false): string {
  if (!s) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (!m) return s;
  return short ? `${m[3]}/${m[2]}` : `${m[3]}/${m[2]}/${m[1]}`;
}

/** Nhãn "+/- (T35/T34)" cho cặp tuần i-1 → i. */
export const pairLabel = (shorts: string[], i: number) => `+/- (${shorts[i]}/${shorts[i - 1]})`;

/** Từ tuyệt đối nên tránh (Logic viết bản tin tuần 16.7). */
export const ABSOLUTE_WORDS = ["hoàn toàn", "100%", "đương nhiên", "chắc chắn", "tuyệt đối"];

/** Các từ tuyệt đối có trong đoạn văn (không phân biệt hoa thường, khớp trọn từ). */
export function findAbsoluteWords(text: string): string[] {
  if (!text.trim()) return [];
  return ABSOLUTE_WORDS.filter((w) => {
    const esc = w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`(?<![\\p{L}\\p{N}])${esc}(?![\\p{L}\\p{N}])`, "iu").test(text);
  });
}

/* Chủ đề Phần IV theo từ khoá tiêu đề (khớp backend `weekly_ai_macro_prompts`): thứ tự xét = ưu tiên,
   khớp từ ĐẦU chữ ('yên' không khớp 'nguyên'); không khớp → vị trí mặc định. Mã nguồn IV.k theo thứ tự
   mặc định (Năng lượng · Cung – Cầu · Tỷ giá & tài chính Nhật · Trung Quốc & khác). */
const MACRO_KEYWORDS: [number, string[]][] = [
  [1, ["năng lượng", "dầu", "butadien"]], [2, ["cung", "cầu", "anrpc"]],
  [3, ["tỷ giá", "yên", "dxy", "tài chính", "lãi suất"]], [4, ["trung quốc", "khác"]],
];

/** Mã mục nguồn tham khảo (IV.k) của tiểu mục IV thứ i theo chủ đề tiêu đề — báo cáo cũ xếp khác vẫn đúng nguồn. */
export function macroSourceCode(title: string, i: number): string {
  const low = (title ?? "").normalize("NFC").toLowerCase();
  const hit = MACRO_KEYWORDS.find(([, kws]) => kws.some((k) => new RegExp(`(?<![\\p{L}\\p{N}_])${k}`, "u").test(low)));
  return `IV.${hit ? hit[0] : i + 1}`;
}

/** Mã mục báo cáo của 1 ô viết — để lọc nguồn tham khảo theo `sections` (Phần IV: xem macroSourceCode). */
export function sectionCodeOf(fieldKey: string): string {
  if (fieldKey.startsWith("macro:")) return `IV.${Number(fieldKey.slice(6)) + 1}`;
  const map: Record<string, string> = {
    summary_prev: "I", movement: "II", exchange_notes: "III.1", physical_notes: "III.2",
    latex_notes: "III.3", forecast: "V", conclusion: "VI",
  };
  return map[fieldKey] ?? "";
}

/** Chỉ cho link http(s) — chặn `javascript:`/`data:` từ danh mục nguồn hay dữ liệu ngoài. null = không render link. */
export function safeHref(url: string | null | undefined): string | null {
  const u = (url ?? "").trim();
  return /^https?:\/\//i.test(u) ? u : null;
}

/** Nối kiểu VN: "A", "A và B", "A, B và C". */
export const joinVi = (items: string[]) =>
  items.length <= 1 ? (items[0] ?? "") : `${items.slice(0, -1).join(", ")} và ${items[items.length - 1]}`;
