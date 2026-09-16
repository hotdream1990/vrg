/* Hook dùng chung cho mọi màn nhập liệu có hàng rào thời gian (cửa sổ sửa · chốt số liệu).

   Màn gọi `saveOrRequest(lưu trực tiếp, bản nháp đề nghị)`: lưu được thì thôi; tài khoản ĐƠN VỊ bị
   server chặn vì hàng rào thời gian thì mở popup gửi Đề nghị sửa với đúng nội dung vừa định lưu.
   Component gọi hook PHẢI render `{modal}`. */

import { useCallback, useRef, useState, type ReactNode } from "react";

import { useAuth } from "../features/auth/AuthContext";
import EditRequestSubmitModal from "../features/command-center/components/EditRequestSubmitModal";
import type { EditRequestOp } from "./edit-request-client";
import { isEditBlocked } from "./http";

export interface EditRequestDraft {
  op: EditRequestOp;
  payload: Record<string, unknown>;
  /** Hiện trong popup: "Biểu Thu mua ngày 01/08/2026". */
  title: string;
  company: string;
  /** Ngày số liệu bị ảnh hưởng ('YYYY-MM-DD') — popup dựng lưu ý chốt theo ngày sớm nhất. */
  dates: string[];
}

export type EditRequestResult = "requested" | "cancelled";

/** Màn đang ở chế độ ĐỀ NGHỊ SỬA mà server vẫn cho lưu thẳng (chỉ đổi ô được phép sửa sau chốt,
 *  hoặc hàng rào đã mở) — báo rõ để đơn vị không chờ Ban duyệt một đề nghị không hề được gửi. */
export const DIRECT_SAVED_IN_REQUEST_MODE = "Đã lưu trực tiếp — nội dung sửa không ảnh hưởng số liệu đã khoá.";

export function useEditRequest(): {
  /** Thử lưu trực tiếp. Tài khoản đơn vị + server chặn vì hàng rào thời gian ⇒ mở popup gửi đề nghị.
   *  Tài khoản khác / lỗi khác ⇒ ném lại như cũ. */
  saveOrRequest(direct: () => Promise<unknown>,
                draft: EditRequestDraft | (() => EditRequestDraft)): Promise<"saved" | EditRequestResult>;
  /** Mở thẳng popup (màn đã biết chắc bản ghi đang khoá). */
  request(draft: EditRequestDraft): Promise<EditRequestResult>;
  modal: ReactNode;
} {
  const { canEditUnitData } = useAuth();
  const [open, setOpen] = useState<{ draft: EditRequestDraft; blocked: string | null } | null>(null);
  const resolver = useRef<((r: EditRequestResult) => void) | null>(null);

  const openModal = useCallback((draft: EditRequestDraft, blocked: string | null) =>
    new Promise<EditRequestResult>((resolve) => {
      resolver.current?.("cancelled");   // popup cũ còn treo (hiếm) → khép lại trước
      resolver.current = resolve;
      setOpen({ draft, blocked });
    }), []);

  const request = useCallback((draft: EditRequestDraft) => openModal(draft, null), [openModal]);

  const saveOrRequest = useCallback(async (
    direct: () => Promise<unknown>, draft: EditRequestDraft | (() => EditRequestDraft),
  ): Promise<"saved" | EditRequestResult> => {
    try {
      await direct();
      return "saved";
    } catch (e) {
      if (!canEditUnitData || !isEditBlocked(e)) throw e;
      return openModal(typeof draft === "function" ? draft() : draft, e.message);
    }
  }, [canEditUnitData, openModal]);

  const finish = (result: EditRequestResult) => {
    const resolve = resolver.current;
    resolver.current = null;
    setOpen(null);
    resolve?.(result);
  };

  const modal = open ? (
    <EditRequestSubmitModal draft={open.draft} blockedMessage={open.blocked}
      onSubmitted={() => finish("requested")} onCancel={() => finish("cancelled")} />
  ) : null;

  return { saveOrRequest, request, modal };
}
