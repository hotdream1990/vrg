/* Gửi thay đổi phương án giá sàn lên server (`POST /api/floor-proposal/apply`) theo HÀNG ĐỢI.
   Server là nguồn tính duy nhất (delta, nội địa theo FOB, làm tròn bước, hoàn tác) nên FE không tự
   cộng trừ gì. Hàng đợi để 2 lần sửa nhanh liên tiếp không cùng gửi một bản cũ — lần sau luôn dựa
   trên bản server vừa trả về, không đè mất lần trước.
   Hook đặt ở màn CHA (Trợ lý AI, màn soạn nháp) để màn cha chờ được hàng đợi rảnh (`whenIdle`)
   rồi mới gửi chat / lưu nháp với phương án mới nhất. */

import { App } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { type Proposal, type ProposalChange, applyProposal } from "../../../../lib/floor-proposal-client";

export type ProposalApplier = {
  /** Trả `true` nếu server nhận thay đổi (ô sửa dùng để quyết định có hoàn lại số cũ không). */
  apply: (changes: ProposalChange[]) => Promise<boolean>;
  busy: boolean;
  /** Chờ mọi lần áp đang xếp hàng xong → phương án MỚI NHẤT (null = chưa có phương án). */
  whenIdle: () => Promise<Proposal | null>;
};

export function useProposalApply(
  proposal: Proposal | null, onChange: (next: Proposal) => void,
): ProposalApplier {
  const { message } = App.useApp();
  const latest = useRef(proposal);
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const [pending, setPending] = useState(0);

  // Phương án bị thay từ bên ngoài (Trợ lý trả bản mới, tải lại bản nháp) → lần áp sau dựa trên bản đó.
  useEffect(() => { latest.current = proposal; }, [proposal]);

  const apply = useCallback((changes: ProposalChange[]): Promise<boolean> => {
    setPending((n) => n + 1);
    const run = queue.current.then(async () => {
      try {
        if (!latest.current) return false;
        const r = await applyProposal(latest.current, changes);
        latest.current = r.proposal;
        onChange(r.proposal);
        (r.warnings ?? []).forEach((w) => message.warning(w));
        return true;
      } catch (e) {
        message.error(e instanceof Error ? e.message : "Không áp dụng được thay đổi.");
        return false;
      } finally {
        setPending((n) => n - 1);
      }
    });
    queue.current = run;
    return run;
  }, [onChange, message]);

  const whenIdle = useCallback(async () => {
    // Trong lúc chờ có thể có lần áp mới xếp thêm (vd blur của ô khác) → chờ tới khi đuôi hàng đợi đứng yên.
    let tail: Promise<unknown>;
    do {
      tail = queue.current;
      await tail;
    } while (tail !== queue.current);
    return latest.current;
  }, []);

  const busy = pending > 0;
  return useMemo(() => ({ apply, busy, whenIdle }), [apply, busy, whenIdle]);
}
