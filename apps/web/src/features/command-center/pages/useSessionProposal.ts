/* Phương án giá sàn NHÁP của phiên Trợ lý AI — chỉ sống trong phiên chat, không ghi biểu giá sàn.
   Giữ thêm ở sessionStorage để lỡ tải lại trang không mất (trình duyệt chặn bộ nhớ → vẫn chạy,
   chỉ mất tiện nghi khôi phục). Khoá theo tên đăng nhập + đăng xuất thì xoá hết (AuthContext):
   người vào sau trên cùng tab không thấy phương án của người trước. */

import { useCallback, useState } from "react";

import type { AdviceLevel } from "../../../lib/assistant-client";
import { type Proposal, SESSION_PROPOSAL_PREFIX, createProposal } from "../../../lib/floor-proposal-client";
import { useAuth } from "../../auth/AuthContext";

function isProposal(v: unknown): v is Proposal {
  const p = v as Proposal | null;
  return !!p && typeof p === "object" && p.version === 1 && typeof p.as_of === "string"
    && Array.isArray(p.rows) && Array.isArray(p.log);
}

function readStored(key: string): Proposal | null {
  try {
    const raw = sessionStorage.getItem(key);
    const parsed: unknown = raw ? JSON.parse(raw) : null;
    return isProposal(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function writeStored(key: string, p: Proposal | null): void {
  try {
    if (p) sessionStorage.setItem(key, JSON.stringify(p));
    else sessionStorage.removeItem(key);
  } catch {
    /* không ghi nhớ được thì thôi — phiên này vẫn chạy đúng */
  }
}

export function useSessionProposal() {
  const { user } = useAuth();
  const key = SESSION_PROPOSAL_PREFIX + (user?.username ?? "");
  const [proposal, setState] = useState<Proposal | null>(() => readStored(key));
  const [creating, setCreating] = useState(false);
  // Đổi tài khoản ngay trên màn (đăng nhập hộ / thoát đăng nhập hộ) → đọc lại theo khoá mới.
  const [loadedKey, setLoadedKey] = useState(key);
  if (loadedKey !== key) {
    setLoadedKey(key);
    setState(readStored(key));
  }

  const setProposal = useCallback((p: Proposal | null) => {
    setState(p);
    writeStored(key, p);
  }, [key]);

  /** Tự lập phương án không cần hỏi AI. "Chỉ tra số" → xuất phát từ giá hiện hành, còn lại → mức mô hình. */
  const create = useCallback(async (advice: AdviceLevel) => {
    setCreating(true);
    try {
      setProposal(await createProposal({ base: advice === "data" ? "current" : "model" }));
    } finally {
      setCreating(false);
    }
  }, [setProposal]);

  return { proposal, setProposal, create, creating };
}
