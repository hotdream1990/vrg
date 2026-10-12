/* Mục 5 phiếu Báo giá mủ — Đề xuất mua từ khách hàng - hàng VRG.
   Một danh sách DÒNG: mỗi dòng tự chọn chủng loại nên cùng chủng loại có thể có nhiều dòng
   (nhiều khách hàng / nhiều nguồn). Chỉ lưu trong phiếu, không mirror sang chuỗi giá. */

import { apiFetch } from "./http";

export type ProposalItem = {
  grade: string;               // chủng loại
  customer: string;            // tên khách hàng — chọn từ danh mục khách hàng của hệ thống
  qty: number | null;          // số lượng (tấn)
  price_vnd: number | null;    // đơn giá (đồng/tấn)
  price_usd: number | null;    // đơn giá (USD/tấn)
  source: string;              // nguồn — tên công ty thành viên
};
export type ProposalSection = { items: ProposalItem[]; note: string };

/** 1 khách hàng trong ô chọn: `units` = số đơn vị thành viên có khách này (tên trùng nhau gộp một dòng). */
export type CustomerOption = { name: string; company: string; units: number };

export const emptyProposal = (): ProposalSection => ({ items: [], note: "" });

export const emptyProposalItem = (): ProposalItem => ({
  grade: "", customer: "", qty: null, price_vnd: null, price_usd: null, source: "",
});

/** Số ô đã điền của 1 dòng. */
const filledCells = (it: ProposalItem): number =>
  [it.grade, it.customer, it.source].filter((s) => s?.trim()).length
  + [it.qty, it.price_vnd, it.price_usd].filter((v) => v != null).length;

export const isProposalItemBlank = (it: ProposalItem): boolean => filledCells(it) === 0;

/** Mục 5 chưa có gì để lưu (dòng trống không tính). */
export const isProposalEmpty = (p?: ProposalSection): boolean =>
  !p || ((p.items ?? []).every(isProposalItemBlank) && !(p.note ?? "").trim());

/** Chép các dòng của phiếu trước sang phiếu đang mở — CHỈ khi phiếu đang mở chưa điền dòng nào
 *  (đã có dòng thì không trộn thêm, tránh lẫn đề xuất của hai ngày). → [mục sau khi chép, số ô đã chép] */
export const fillProposalFromPrev = (
  dst: ProposalSection | undefined, src?: ProposalSection,
): [ProposalSection, number] => {
  const cur = dst ?? emptyProposal();
  if (!(cur.items ?? []).every(isProposalItemBlank)) return [cur, 0];
  const rows = (src?.items ?? []).filter((it) => !isProposalItemBlank(it));
  return [{ ...cur, items: rows.map((it) => ({ ...it })) }, rows.reduce((n, it) => n + filledCells(it), 0)];
};

/** Tìm khách hàng Ở SERVER (danh mục khách của mọi đơn vị rất dài) — gõ không dấu cũng ra. */
export const fetchCustomerOptions = (q: string) =>
  apiFetch<CustomerOption[]>(`/api/market-quote/customer-options${q ? `?${new URLSearchParams({ q })}` : ""}`);
