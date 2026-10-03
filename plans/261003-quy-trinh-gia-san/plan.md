# Quy trình điều chỉnh giá sàn: Nháp → Dự thảo → Tờ trình → Áp dụng

Ngày: 03/10/2026 · Nhánh: `claude/sleepy-shannon-yii403` · Nền: bản nháp tờ trình
([260924-ban-nhap-gia-san-tro-ly](../260924-ban-nhap-gia-san-tro-ly/plan.md)).

## Yêu cầu (chủ dự án)
1. Làm sâu quy trình dự báo giá sàn: soạn → chỉnh → xuất hình dự thảo → tờ trình → áp dụng.
2. Ô sửa được phải trông như ô nhập (input box có viền) để dễ nhận ra.
3. Chép được **hình dự thảo điều chỉnh giá sàn** (như bảng Excel "DỰ THẢO GIÁ SÀN ĐIỀU CHỈNH").
4. Xuất **tờ trình theo mẫu mới** (Tờ trình số 54/TTr-TTKD, lần 22 ngày 24/9/2026).
5. Sửa được nội dung tờ trình; ưu tiên **AI soạn** (như Báo cáo tuần), hợp lý với mức giá thay đổi.
6. Chia bước: **Nháp → Dự thảo → Tờ trình → Áp dụng**. Áp dụng: có trong quy trình, **chưa làm**
   (không ghi biểu giá sàn chính thức, không apply ngược).

## Quyết định
- Bước gắn vào bản nháp sẵn có (`floor_draft.stage`), bản cũ = `nhap`. Không thêm bảng mới.
- Mỗi phần chỉ sửa ở đúng bước của nó, server chặn: số (phương án) ở **Nháp** · tỷ giá VCB ở **Dự
  thảo** · nội dung tờ trình ở **Tờ trình** · **Áp dụng** khoá hết (và hiện chưa chuyển tới được).
- Đi tới từng nấc; **trả về thẳng bước bất kỳ phía trước** kèm lý do (03/10: lãnh đạo không duyệt tờ trình →
  về Nháp sửa số). Lui không xoá gì: nội dung tờ trình giữ lại; số đổi so với lúc soạn/soát nội dung →
  cảnh báo "cần soát lại" (so `memo.sig` với chữ ký số phương án hiện tại), bấm "Đã soát" để tắt.
- Hình dự thảo + PDF tờ trình dựng ở SERVER bằng Chromium (Playwright có sẵn trong image) → hình chép
  ra giống hệt bản xem. Word (.docx) dựng bằng `python-docx` (thêm phụ thuộc).
- Mẫu tờ trình mới thay mẫu cũ ở MỌI chỗ xem trước (Trợ lý AI, Gợi ý giá sàn); thiếu nội dung tờ trình
  thì dùng nội dung mặc định dựng từ số.
- AI chỉ là bản nháp cho chuyên viên: trả về để xem/sửa, KHÔNG tự lưu; kèm cảnh báo số không đối
  chiếu được, từ ngữ tuyệt đối, và lệch chiều so với phương án (phương án tăng mà văn kết luận giảm…).

## HỢP ĐỒNG API (bổ sung)

```ts
type Stage = "nhap" | "du_thao" | "to_trinh" | "ap_dung";
type Para = { lead: string; text: string };        // lead in đậm-nghiêng (vd "OSE (Osaka Exchange) – RSS3:")
type Sheet = { vcb_rate: number | null; vcb_time: string; vcb_date: string | null };  // chú thích hình dự thảo
type Signers = { left_role: string; left_name: string; right_role: string; right_name: string;
                 approver_role: string; approver_name: string };
type Memo = {
  so: string;                  // "54/TTr-TTKD" — trống thì in "……/TTr-TTKD"
  sign_date: string;           // ngày ghi trên tờ trình (YYYY-MM-DD)
  futures_note: string;        // "Nguồn: …" dưới bảng I (nghiêng, chữ nhỏ)
  futures: Para[];             // diễn giải mục I theo từng sàn
  physical_title: string;      // đuôi tiêu đề mục II, vd "tham chiếu giá nguồn từ ANRPC các ngày 21/9 và 22/9"
  physical_note: string;       // đoạn ngay dưới bảng II
  physical: Para[];            // diễn giải mục II
  outlook: Para[];             // cung – cầu / triển vọng
  inventory: Para;             // lead đậm "Tồn kho Tập đoàn lũy kế tuần 37: …" + text
  intro: string;               // "Ban TTKD kính trình Tổng giám đốc phê duyệt điều chỉnh giá sàn lần thứ …"
  signers: Signers;
  sig: string;                 // chữ ký số phương án lúc nội dung được soạn/soát
  ai: { at: string; by: string | null; sig: string; warnings: string[] } | null;
};
// Draft thêm:
type Draft = { /* …cũ… */ stage: Stage; sheet: Sheet | null; memo: Memo | null; sig: string;
               history: { from: Stage; to: Stage; at: string; by: string | null; note: string | null }[] };
type DraftSummary = { /* …cũ… */ stage: Stage };
```

| Method | Path | Body | Trả |
|---|---|---|---|
| PUT | `/api/floor-proposal/drafts/{id}` | thêm `sheet?`, `memo?` | `Draft` · 400 nếu sửa phần không thuộc bước hiện tại |
| POST | `/api/floor-proposal/drafts/{id}/stage` | `{to: Stage, note?, base_updated_at?}` | `Draft` · tới 1 nấc, lui bước bất kỳ · 400 nhảy cóc tới / thiếu số / Áp dụng · 409 xung đột |
| POST | `/api/floor-proposal/drafts/{id}/memo/ai` | `{memo?: Memo}` | `{memo: Memo, warnings: string[]}` (không lưu) |
| GET | `/api/floor-proposal/drafts/{id}/du-thao.png` | — | `image/png` hình dự thảo (bản đã lưu) |
| GET | `/api/floor-proposal/drafts/{id}/to-trinh.pdf` | — | PDF tờ trình (bản đã lưu) |
| GET | `/api/floor-proposal/drafts/{id}/to-trinh.docx` | — | Word tờ trình (bản đã lưu) |
| POST | `/api/floor-proposal/preview` | thêm `memo?` | HTML mẫu mới |

Quyền: như bản nháp (`floor_suggest`; ghi cần mức Sửa — Lãnh đạo Tập đoàn chỉ xem/tải).

## Todo
- [x] Backend bước + khoá theo bước + test (`test_floor_draft_flow.py`)
- [x] Hình dự thảo (PNG) · tờ trình mẫu mới (HTML/PDF/DOCX) + test
- [x] AI soạn nội dung tờ trình + cảnh báo + test LLM giả (`test_to_trinh_memo_ai.py`)
- [x] Frontend: thanh bước, ô nhập có viền, dự thảo (chép hình), tờ trình (sửa · AI · xuất)
- [x] Kiểm thử trình duyệt (dữ liệu mẫu lần 22/2026, LLM giả), changelog, knowledge
- [ ] Chạy AI với khoá thật trên prod, soát chất lượng văn
- [ ] Bước Áp dụng (ghi `vrg_floor_price` sau khi TGĐ duyệt) — chủ dự án chưa yêu cầu

## Ghi chú
- Số tuần ở dòng tồn kho theo tuần ISO (như Báo cáo tuần): 17/09/2026 = tuần 38; mẫu 54/TTr ghi "tuần 37".
  Dòng này sửa tay được — cần thống nhất cách đánh số với Ban TTKD nếu muốn tự khớp.
- Máy dev chạy Chromium của Playwright Python phải trỏ `PLAYWRIGHT_BROWSERS_PATH` tới bản trình duyệt khớp
  phiên bản; image prod có sẵn (cùng đường xuất PDF bản tin / báo cáo tuần).
