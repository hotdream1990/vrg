-- Bù tỷ giá USD/JPY · USD/CNY · USD/THB ngày 03/09 → 11/09/2026 (Thứ 2–6; 21 dòng). CHƯA CHẠY.
-- Nguồn: x-rates.com Historical Rates — Close ngày D = trang ngày D+1 (ảnh chụp ~00:00 UTC),
-- đúng quy tắc của crawler mới (services/crawlers/crawlers/macro/fx.py). Lấy từ CHÍNH container prod.
-- Làm tròn theo quy ước lưu: USD/JPY 2 số lẻ nửa-lên (price_repo.r2) · CNY/THB 4 số lẻ.
-- Không có 05-06/09 và 12/09 (cuối tuần — sàn nghỉ; không nhân bản giá thứ Sáu).
-- ON CONFLICT DO NOTHING: nếu crawler mới đã kịp ghi ngày nào (cùng số) thì giữ nguyên, không đè tay.
\set ON_ERROR_STOP on
BEGIN;
INSERT INTO fact_price (as_of, source, grade, contract, price_type, price, currency, unit)
VALUES
  ('2026-09-03', 'fx', 'USD/JPY', '', 'fx', 155.65, 'JPY', 'JPY per USD'),
  ('2026-09-03', 'fx', 'USD/CNY', '', 'fx', 6.7191, 'CNY', 'CNY per USD'),
  ('2026-09-03', 'fx', 'USD/THB', '', 'fx', 32.9005, 'THB', 'THB per USD'),
  ('2026-09-04', 'fx', 'USD/JPY', '', 'fx', 156.26, 'JPY', 'JPY per USD'),
  ('2026-09-04', 'fx', 'USD/CNY', '', 'fx', 6.7119, 'CNY', 'CNY per USD'),
  ('2026-09-04', 'fx', 'USD/THB', '', 'fx', 32.9185, 'THB', 'THB per USD'),
  ('2026-09-07', 'fx', 'USD/JPY', '', 'fx', 153.83, 'JPY', 'JPY per USD'),
  ('2026-09-07', 'fx', 'USD/CNY', '', 'fx', 6.7116, 'CNY', 'CNY per USD'),
  ('2026-09-07', 'fx', 'USD/THB', '', 'fx', 32.8585, 'THB', 'THB per USD'),
  ('2026-09-08', 'fx', 'USD/JPY', '', 'fx', 153.48, 'JPY', 'JPY per USD'),
  ('2026-09-08', 'fx', 'USD/CNY', '', 'fx', 6.7102, 'CNY', 'CNY per USD'),
  ('2026-09-08', 'fx', 'USD/THB', '', 'fx', 32.9094, 'THB', 'THB per USD'),
  ('2026-09-09', 'fx', 'USD/JPY', '', 'fx', 153.55, 'JPY', 'JPY per USD'),
  ('2026-09-09', 'fx', 'USD/CNY', '', 'fx', 6.708, 'CNY', 'CNY per USD'),
  ('2026-09-09', 'fx', 'USD/THB', '', 'fx', 32.9324, 'THB', 'THB per USD'),
  ('2026-09-10', 'fx', 'USD/JPY', '', 'fx', 154.48, 'JPY', 'JPY per USD'),
  ('2026-09-10', 'fx', 'USD/CNY', '', 'fx', 6.7071, 'CNY', 'CNY per USD'),
  ('2026-09-10', 'fx', 'USD/THB', '', 'fx', 33.1621, 'THB', 'THB per USD'),
  ('2026-09-11', 'fx', 'USD/JPY', '', 'fx', 153.58, 'JPY', 'JPY per USD'),
  ('2026-09-11', 'fx', 'USD/CNY', '', 'fx', 6.7068, 'CNY', 'CNY per USD'),
  ('2026-09-11', 'fx', 'USD/THB', '', 'fx', 33.0703, 'THB', 'THB per USD')
ON CONFLICT (as_of, source, grade, price_type) DO NOTHING;
SELECT grade, count(*) AS so_ngay, min(as_of), max(as_of)
  FROM fact_price WHERE source='fx' AND grade IN ('USD/JPY','USD/CNY','USD/THB')
   AND as_of BETWEEN '2026-09-03' AND '2026-09-11' GROUP BY grade ORDER BY grade;  -- kỳ vọng mỗi cặp 7 ngày
COMMIT;
