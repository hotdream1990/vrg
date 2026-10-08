# Review 7dc380d: support close/reopen rule (26/09/2026)

**Verdict: nothing must change.** Server and web implement rules 1–5 exactly.
- `_thread_in_scope` (404) still runs before `assert_may_set_status`, and the UPDATE stays company-filtered.
- `kind` comes from the DB. Both sides treat any kind other than `request` as sent by HQ, so an unknown kind stays blocked.
- A stale web bundle gets the Vietnamese 403.
- The extracted `SupportReplyBox` behaves the same: `load()` swaps the page to a spinner, so the box remounts empty.
- `tsc --noEmit` on the whole web app: 0 errors. `ruff check`: clean.

## Findings (all optional, most useful first)

1. **The status endpoint's isolation check has no test.** At `apps/api/tests/test_support.py:302`, add `assert client.put(f"/api/support/threads/{tid}/status", json={"status": "closed"}, headers=env["b"]).status_code == 404`. In `test_chi_xem_thi_khong_gui_duoc` (line 181), assert that a view-only HQ account gets 403 on PUT status.
2. **Follow-ups outside this commit:**
   - `docs/huong-dan/lanh-dao-don-vi/README.md:63,97,129,335` still tells units to press "Đánh dấu đã xong" on notices and reminders. The `spec.json`/`shoot.py` fixes are uncommitted in the working tree. Regenerate the README and images 03 and 07, and commit them with this fix.
   - No changelog entry yet. The 29/08 entry (`project-changelog.md:244`) says both sides can close.
   - The 6 notices closed on 26/09 are still closed. HQ must "Mở lại" them.
3. **Wording (low).**
   - `SupportThreadPage.tsx:69-70`: units only see this dialog for their own requests, so "Còn kết quả cần báo" reads like the notice case. Suggest "Còn điều gì cần trao đổi, vui lòng gửi phản hồi trước."
   - `SupportReplyBox.tsx:67` says "thông báo này" on reminder and alert threads too. "ngay trong thẻ này" fits every kind.
4. **Size (low).** `support.py` is now exactly 200 lines; the rule is under 200. Next change should move the two `/file` endpoints to `support_files.py`.
5. **Label (optional).** The button still says "Đánh dấu đã xong", the label that was misread. The dialog says "Khép thẻ" and the tag says "Đã đóng". Consider "Khép thẻ" when the guide is regenerated.

## Open question

Units can no longer close reminder or alert threads. Every HQ-sent thread now stays open until HQ closes it one by one, with a confirm each time. That includes the daily anomaly alerts to 63 units, if that job is on. Should `SupportBatchPage` get a "Khép cả đợt" (close the whole batch) action?
