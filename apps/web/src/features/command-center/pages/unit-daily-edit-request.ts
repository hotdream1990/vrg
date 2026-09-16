/* Bản nháp «Đề nghị sửa» cho biểu Thu mua / Tồn kho (api-contract §1: `daily_report` · `daily_move`).
   Payload = đúng thứ màn định lưu, để Ban duyệt xong hệ thống ghi lại y nguyên. */

import { dmy } from "../../../lib/date";
import type { MemberPriceType } from "../../../lib/member-client";
import type { PriceDraft, UnitPurchasePrice } from "../../../lib/unit-daily-client";
import { KIND_LABEL, type Kind, type Values } from "../../../lib/unit-daily-fields";
import type { EditRequestDraft } from "../../../lib/use-edit-request";

/** Loại giá → khoá trong kho giá (`price_type`). */
export type PriceChanges = Partial<Record<MemberPriceType, number>>;

const PRICE_SLOTS: [keyof PriceDraft, MemberPriceType][] = [
  ["latex", "purchase"], ["cup", "purchase_cup"], ["lace", "purchase_lace"],
];

/** Chỉ loại giá THAY ĐỔI so với đang lưu. Giá trị 0 = xoá ô giá ("ngày đó không có giá" — kho giá
 *  không lưu số 0, xem `app/core/market_meta.py`), khớp luật `upsert_record` ở server. */
export const priceChanges = (prices: PriceDraft, orig: UnitPurchasePrice | null | undefined): PriceChanges =>
  Object.fromEntries(PRICE_SLOTS.flatMap(([slot, pt]) => {
    const next = prices[slot] === 0 ? null : (prices[slot] ?? null);
    return next === (orig?.[slot] ?? null) ? [] : [[pt, next ?? 0]];
  }));

/** `createOnly` = nút Thêm (đúng thân API ghi thẳng) — lúc gửi mà ngày đó đã có số thì server trả 409. */
export const dailyReportDraft = (
  kind: Kind, company: string, asOf: string, fields: Values, prices?: PriceChanges, createOnly = false,
): EditRequestDraft => ({
  op: "daily_report",
  // Biểu Thu mua gom CẢ đơn giá vào cùng một đề nghị — không để phần biểu bị chặn mà phần giá lọt đi riêng.
  payload: {
    kind, company, as_of: asOf, fields,
    ...(kind === "purchase" ? { prices: prices ?? {} } : {}),
    ...(createOnly ? { create_only: true } : {}),
  },
  title: `Biểu ${KIND_LABEL[kind]} ngày ${dmy(asOf)}`,
  company,
  dates: [asOf],
});

export const dailyMoveDraft = (kind: Kind, company: string, asOf: string, toDate: string): EditRequestDraft => ({
  op: "daily_move",
  payload: { kind, company, as_of: asOf, to_date: toDate },
  title: `Đổi ngày biểu ${KIND_LABEL[kind]} ${dmy(asOf)} → ${dmy(toDate)}`,
  company,
  dates: [asOf, toDate],
});
