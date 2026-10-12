-- Bù tỷ giá USD/MYR ngày 28/09 → 05/10/2026 (Thứ 2–6; 6 dòng). ĐÃ CHẠY trên prod 12/10/2026 (INSERT 6).
-- Sự cố: từ 28/09 12:00 đến 06/10 18:00 (giờ VN) mọi lượt quét báo "MYR (BNM) lỗi" → thiếu USD/MYR
-- → giá Latex MRB (Sen/kg) các ngày này không quy được ra USD/T (bản tin/Bảng các sàn để trống).
-- Nguồn: api.bnm.gov.my /exchange-rate/USD/year/2026/month/{9,10}?session=1200&quote=rm,
-- trường buying_rate (đúng nguồn crawler hằng ngày + chuyên viên). Lấy từ chính server prod 12/10/2026.
-- Đối chiếu: các ngày đã có trên prod (25/09 = 4,075 · 06/10 = 4,083 · 07/10 = 4,0845 · 08/10 = 4,085 ·
-- 09/10 = 4,086) khớp từng số với API tháng → cùng nguồn, không lệch.
-- Làm tròn 4 số lẻ như crawler. Không có 26-27/09, 03-04/10 (cuối tuần).
-- ON CONFLICT DO NOTHING: nếu crawler đã kịp ghi ngày nào thì giữ nguyên, không đè.
\set ON_ERROR_STOP on
BEGIN;
INSERT INTO fact_price (as_of, source, grade, contract, price_type, price, currency, unit)
VALUES
  ('2026-09-28', 'fx', 'USD/MYR', '', 'fx', 4.082, 'MYR', 'MYR per USD'),
  ('2026-09-29', 'fx', 'USD/MYR', '', 'fx', 4.079, 'MYR', 'MYR per USD'),
  ('2026-09-30', 'fx', 'USD/MYR', '', 'fx', 4.077, 'MYR', 'MYR per USD'),
  ('2026-10-01', 'fx', 'USD/MYR', '', 'fx', 4.084, 'MYR', 'MYR per USD'),
  ('2026-10-02', 'fx', 'USD/MYR', '', 'fx', 4.083, 'MYR', 'MYR per USD'),
  ('2026-10-05', 'fx', 'USD/MYR', '', 'fx', 4.085, 'MYR', 'MYR per USD')
ON CONFLICT (as_of, source, grade, price_type) DO NOTHING;

-- Đối chiếu: phải ra 6 dòng, rồi Latex 6 ngày này có USD/MYR cùng ngày (0 ngày còn thiếu).
SELECT as_of, price FROM fact_price
 WHERE source = 'fx' AND grade = 'USD/MYR' AND as_of BETWEEN '2026-09-28' AND '2026-10-05' ORDER BY as_of;
SELECT count(*) AS latex_thieu_ty_gia FROM fact_price l
 WHERE l.source = 'lgm' AND l.grade = 'LATEX' AND l.as_of >= '2026-09-01'
   AND NOT EXISTS (SELECT 1 FROM fact_price f WHERE f.source = 'fx' AND f.grade = 'USD/MYR' AND f.as_of = l.as_of);
COMMIT;
