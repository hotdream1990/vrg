/* Bản nháp «Đề nghị sửa» cho hợp đồng / đợt giao (api-contract §1: `contract_save` · `contract_delete`).
   Hàng rào thời gian của hợp đồng tính theo NGÀY GIAO — ngày số liệu bị ảnh hưởng là ngày giao cũ + mới. */

import type { Contract } from "../../../../lib/sales-contract-client";
import type { EditRequestDraft } from "../../../../lib/use-edit-request";

const noun = (c: Pick<Contract, "parent_id">) => (c.parent_id ? "Đợt giao" : "Hợp đồng");

const uniqDates = (...dates: (string | null | undefined)[]): string[] =>
  [...new Set(dates.filter((d): d is string => !!d))];

/** `body` = đúng thân `PUT /api/sales-contracts` màn định gửi; `before` = bản ghi đang lưu (null = thêm mới). */
export const contractSaveDraft = (body: Contract, before: Contract | null | undefined): EditRequestDraft => ({
  op: "contract_save",
  payload: body as unknown as Record<string, unknown>,
  title: `${noun(body)} ${body.code}`,
  company: body.company,
  dates: uniqDates(before?.delivered_at, body.delivered_at),
});

/** Chuyển loại giao (giao 1 lần ↔ giao nhiều lần) — thao tác riêng, không nằm trong `contract_save`:
 *  đổi loại giao còn kéo theo việc dời lần giao xuống đợt giao đầu tiên. */
export const contractDeliveryTypeDraft = (c: Contract, to: "single" | "multi"): EditRequestDraft => ({
  op: "contract_delivery_type",
  payload: { id: c.id, delivery_type: to },
  title: `Hợp đồng ${c.code} — chuyển sang ${to === "multi" ? "giao nhiều lần" : "giao 1 lần"}`,
  company: c.company,
  dates: uniqDates(c.delivered_at),
});

export const contractDeleteDraft = (c: Contract): EditRequestDraft => ({
  op: "contract_delete",
  payload: { id: c.id },
  title: `Xoá ${noun(c).toLowerCase()} ${c.code}`,
  company: c.company,
  dates: uniqDates(c.delivered_at),
});

/** Câu hỏi trước khi xoá. `locked` = đã quá hạn sửa ở phía web → nói trước là sẽ thành đề nghị. */
export const deleteConfirmText = (label: string, locked: boolean) => (locked
  ? `Xoá ${label}?\n\nBản ghi đã quá hạn sửa: hệ thống sẽ mở hộp gửi đề nghị xoá, Ban duyệt xong mới xoá thật.`
  : `Xoá ${label}?`);
