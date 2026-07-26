/** Danh sách chứng từ đính kèm (NHIỀU file) của 1 ô đính kèm.
 *
 *  Đối xứng với `apps/api/app/services/contract_docs.py`. Mỗi ô giữ danh sách file, đồng thời
 *  vẫn ghi file ĐẦU vào cặp khoá phẳng cũ `(file, filename)` — nhờ vậy bản ghi cũ (chỉ có 1 file
 *  ở cặp khoá cũ) đọc lên vẫn đúng, KHÔNG phải chuyển đổi dữ liệu đã lưu.
 */

export type ContractDoc = { file: string; filename: string };

/** Trần số file mỗi ô — khớp `MAX_DOCS` phía server. */
export const MAX_DOCS = 20;

/** Danh sách chứng từ của 1 ô: ưu tiên danh sách mới, thiếu thì dựng từ cặp khoá phẳng cũ. */
export function docsOf(
  list: ContractDoc[] | null | undefined,
  legacyFile?: string | null,
  legacyName?: string | null,
): ContractDoc[] {
  const out = (list ?? []).filter((d) => d && d.file);
  if (out.length) return out;
  return legacyFile ? [{ file: legacyFile, filename: legacyName || legacyFile }] : [];
}

/** Bản vá để gán danh sách MỚI vào 1 dòng: ghi cả danh sách lẫn cặp khoá cũ (file đầu). */
export function docsPatch<K extends string, F extends string, N extends string>(
  listKey: K, fileKey: F, nameKey: N, docs: ContractDoc[],
): Record<string, unknown> {
  const capped = docs.slice(0, MAX_DOCS);
  return {
    [listKey]: capped,
    [fileKey]: capped[0]?.file ?? null,
    [nameKey]: capped[0]?.filename ?? null,
  };
}
