# Hợp đồng: đổi “phụ lục” → “đợt giao” + vòng đời hợp đồng (05/08/2026)

Nguồn: phản hồi của khách ngày 05/08/2026 (5 gạch đầu dòng + ghi chú về hợp đồng khung).
Nhánh `feature/contract-management`, tiếp nối [../260730-feedback-vrg-hop-dong-khach-hang](../260730-feedback-vrg-hop-dong-khach-hang).

## Chốt nghiệp vụ

1. **“Phụ lục” đổi thành “ĐỢT GIAO.”** Một hợp đồng có thể giao nhiều lần; mỗi lần là một đợt gồm
   **hoá đơn (số + file) · ngày giao · chủng loại + số lượng + đơn giá**,
   kèm **một lần thanh toán** (giữ nguyên như cũ).
   - Bỏ ô **“Ngày bắt đầu (mở đợt)”** — sinh ra để tính khối 3 theo từng đợt, nay hết vai trò.
   - **Số đợt giao vẫn nhập tay** (không trùng trong đơn vị), như số phụ lục trước đây.
2. **Chuyển giao-1-lần ↔ giao-nhiều-lần ngay trên giao diện**, không phải xoá nhập lại. Nếu hợp
   đồng đã ghi một lần giao thì lần giao đó **tự chuyển thành đợt giao đầu tiên** (giữ ngày giao,
   hoá đơn, thanh toán, dòng chi tiết). Còn đợt giao thì không quay ngược về
   giao-1-lần được (phải xoá hết đợt trước).
3. **“Đã ký HĐ chưa giao” tính trên HỢP ĐỒNG CHÍNH**: `sản lượng hợp đồng − đã giao`, tính từ
   **ngày ký**. Trước đây chỉ phần đã chia thành đợt mới được tính.
4. **Thực giao được lệch so với hợp đồng** (thực tế quanh 5%): cho nhập vượt, **chặn ở 110%**;
   vượt 100% thì cảnh báo vàng nhưng vẫn lưu. Giao thiếu thì bấm **Hoàn thành hợp đồng** để chốt
   ngày kết thúc — phần chênh còn lại rời khỏi “đã ký HĐ chưa giao” **kể từ ngày chốt**. Hợp đồng
   đã chốt bị khoá sửa; bấm nhầm thì **Mở lại hợp đồng**.
5. **KHÔNG quản lý hợp đồng khung (hợp đồng dài hạn).** Đơn vị có hợp đồng dài hạn thì nhập
   **mỗi phụ lục như một hợp đồng chuyến** và chọn loại **“HĐ dài hạn”** để phân biệt loại. Đây
   cũng là lý do khối 3 tính được trên hợp đồng mà không bị thổi phồng.

## Ảnh hưởng số liệu (cần nói rõ với đơn vị)

- **“Đã ký HĐ chưa giao” sẽ TĂNG** so với cách tính cũ, vì nay gồm cả phần hàng chưa sản xuất.
- Vì vậy **bỏ cảnh báo “khối 3 > tồn kho thành phẩm”** ở lưới Tồn kho: theo cách tính mới, vượt
  tồn kho thành phẩm là chuyện bình thường, để lại thì cảnh báo hiện gần như mọi dòng.
- Hợp đồng cũ (đã chuyển từ cơ chế cũ) **không phải nhập lại**: ô “ngày mở đợt” chỉ ẩn khỏi form,
  dữ liệu vẫn giữ trong CSDL.
- Đơn vị nên rà lại các hợp đồng **đã giao xong nhưng thiếu/thừa vài %** và bấm *Hoàn thành hợp
  đồng*, nếu không phần chênh sẽ treo mãi ở “đã ký HĐ chưa giao”.

## Thay đổi kỹ thuật

| Lớp | Nội dung |
|---|---|
| CSDL | `sales_contract` thêm `invoice_no` · `invoice_docs` · `completed_at` (idempotent trong `apps/api/app/core/db.py`) |
| Backend | `sales_contract_clean.py` (tách phần kiểm tra) · `sales_contract_lifecycle.py` (hoàn thành / chuyển loại giao) · `sales_contract_repo.MAX_OVER_RATIO = 1.10` · `sales_contract_report.undelivered_on` viết lại (gom ở SQL) |
| API | `PUT /api/sales-contracts/{id}/completion` · `PUT /api/sales-contracts/{id}/delivery-type` · bộ lọc trạng thái thêm `completed` · chi tiết trả thêm `over_qty`, `max_qty` |
| Web | `ContractBatchDocs` · `ContractBatchTable` · `ContractCompleteModal`; danh sách đổi cột (SL hợp đồng · Đã giao · Còn phải giao · Đợt giao · Trạng thái); menu “Hợp đồng & đợt giao” |

## Kiểm thử

- `apps/api`: 168 pytest pass · ruff sạch. Test mới: trần 110%, hoàn thành → khối 3, khoá khi đã
  chốt, chuyển loại giao giữ nguyên lần giao, hoá đơn lưu + tải được file.
- `apps/web`: `pnpm build` sạch; thử tay trên trình duyệt cả 3 luồng (chuyển loại giao · cảnh báo
  vượt 6% · chặn vượt 16% · hoàn thành + mở lại).

## Việc còn lại khi deploy

- Chạy bản mới là schema tự thêm cột (không cần script riêng).
- Nhắc đơn vị: khối 3 tăng là do đổi cách tính, và cần bấm *Hoàn thành hợp đồng* cho các hợp đồng
  đã kết thúc.
- Cập nhật file hướng dẫn nhập liệu cho đơn vị (`docs/huong-dan/`) theo tên gọi mới.
