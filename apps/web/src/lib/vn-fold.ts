/* Bỏ dấu tiếng Việt để TÌM không dấu: gõ "tay nguyen" vẫn ra "Tây Nguyên". */

export const foldVi = (s: string): string =>
  s.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/gi, "d").toLowerCase();

/** `filterOption` cho ô chọn antd có tìm kiếm tại chỗ (khớp theo nhãn, không dấu). */
export const foldFilterOption = (input: string, opt?: { label?: unknown }): boolean =>
  foldVi(String(opt?.label ?? "")).includes(foldVi(input));
