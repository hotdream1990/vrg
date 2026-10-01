-- 01/10/2026 — Đổi các hợp đồng đang gắn hồ sơ mẹ (HĐNT/HĐDH) mà loại vẫn là "HĐ chuyến" sang
-- "Phụ lục hợp đồng mẹ" (contract_type = 'long_term'). Chủ dự án chốt: HĐ chuyến không có hợp đồng mẹ.
-- Báo cáo KHÔNG đổi số vì từ bản này đã xếp nhóm theo hồ sơ mẹ — chỉ gỡ kẹt form sửa
-- ("HĐ chuyến không có hợp đồng mẹ" mà không có ô gỡ). Đo prod 01/10: 76 hợp đồng (63 HĐNT · 13 HĐDH).
-- Chạy SAU khi deploy bản xếp nhóm theo hồ sơ mẹ. Trước khi chạy: xuất bản sao (bước 1) ra file.

-- Bước 1 (chỉ đọc) — bản sao để khôi phục:
-- \copy (SELECT id, company, code, contract_type, updated_by, updated_at FROM sales_contract
--        WHERE parent_id IS NULL AND master_id IS NOT NULL AND contract_type IS DISTINCT FROM 'long_term')
--        TO 'backup-hd-chuyen-gan-ho-so.csv' CSV HEADER

BEGIN;
SELECT count(*) AS se_doi FROM sales_contract
 WHERE parent_id IS NULL AND master_id IS NOT NULL AND contract_type IS DISTINCT FROM 'long_term';

UPDATE sales_contract
   SET contract_type = 'long_term', updated_by = 'sqlfix-20261001-phu-luc', updated_at = now()
 WHERE parent_id IS NULL AND master_id IS NOT NULL AND contract_type IS DISTINCT FROM 'long_term';

SELECT count(*) AS con_lai FROM sales_contract
 WHERE parent_id IS NULL AND master_id IS NOT NULL AND contract_type IS DISTINCT FROM 'long_term';
COMMIT;
