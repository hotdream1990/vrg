# Cải tiến mô hình gợi ý giá sàn + Backtest toàn chuỗi

> Mục tiêu: (A) nâng độ chính xác dự báo giá sàn Tập đoàn, (B) kiểm định mô hình trên
> toàn bộ lịch sử ban hành để đo "độ khớp" khách quan giữa dự báo và giá sàn thực tế.
> Liên quan: [[floor-suggest-feature]] · [[gia-san-issuance-process]]

## Bối cảnh hiện trạng (v1)
- `services/floor_suggest.py`: hồi quy **đơn biến** `floor ≈ a + b·basket`, basket = TB z-score của
  4 chỉ số (MRB SMR20, SGX TSR20, SHFE RU, OSE RSS3). Backtest chỉ tại 1 lần.
- DB: 30 lần ban hành (2024-01→2026-06, 13 grades); predictor phủ tốt (mủ nước 1874, lgm 1449,
  sgx 1002, shfe 572, tocom 547 dòng).

## 3 vấn đề cần xử lý
1. **Look-ahead bias**: `_basket()` chuẩn hoá z-score trên TOÀN chuỗi (kể cả tương lai) rồi mới
   cắt train → backtest lạc quan giả. Phải chuẩn hoá CAUSAL (chỉ trên train).
2. **Bỏ predictor mạnh nhất**: giá mủ nước (r=0.92) không nằm trong model.
3. **Thiếu backtest toàn chuỗi + metric tổng hợp** (MAPE/MAE/RMSE + % đúng hướng).

## Quyết định (đã chốt với user)
- Model: **hồi quy đa biến (ridge) + giá mủ nước**, có regularization vì n nhỏ (~30).
- Thư viện: **cho phép numpy**.
- Thứ tự: dựng backtest harness trước (đo baseline v1 khách quan) → improve v2 → so qua harness.

---

## Phase 1 — Backend: model + backtest engine
**Files**
- `apps/api/pyproject.toml`: thêm `numpy>=2.0`.
- TẠO `apps/api/app/services/floor_model.py` (<200 dòng): đại số tuyến tính thuần numpy.
  - `standardize(train_X)` → (mean, sd) trên TRAIN; `apply(x, mean, sd)`.
  - `ridge_fit(X, y, alpha)` → β (không phạt intercept) qua normal equations.
  - `predict(beta, x_std)`.
  - `metrics(actual, pred)` → {mae, mape, rmse, r2}; `hit_rate(actual, pred)` trên Δ liên tiếp.
- SỬA `apps/api/app/services/floor_suggest.py`:
  - Feature set v2: `[mu_nuoc, lgm:SMR20, sgx:TSR20, shfe:RU, tocom:RSS3]` (raw, latest ≤ as_of).
  - `_features(fd, idx)` → ma trận X theo từng lần ban hành (None nếu thiếu).
  - `_fit_at(train_idx, target_idx, grade, model, alpha)`: bỏ feature thiếu phủ trên train, bỏ
    dòng train thiếu giá trị, chuẩn hoá CAUSAL, ridge fit, dự báo target. `model="v1"` = giữ
    basket đơn biến (đã sửa causal); `model="v2"` = đa biến ridge.
  - `suggest(as_of, model, backtest)`: tái dùng `_fit_at` (mặc định v2).
  - `backtest(grade, model, alpha)`: walk-forward expanding window (min_train=8), trả per-lần
    {as_of, lan, actual, pred, err, err_pct} + summary {mae, mape, rmse, hit, r2, n}.
  - `backtest_summary(model, alpha)`: MAPE/hit/n cho cả 13 grade (SVR 10 đầu bảng).
- SỬA `apps/api/app/routers/floor_suggest.py`: thêm `GET /backtest`, `GET /backtest/summary`;
  `suggest`/`/` thêm query `model`.

## Phase 2 — Frontend: màn kiểm định
**Files**
- SỬA `lib/floor-suggest-client.ts`: types + `fetchBacktest`, `fetchBacktestSummary`; thêm `model`.
- TẠO `charts/BacktestChart.tsx` (<200 dòng): 2 đường predicted vs actual theo thời gian (chart.js).
- TẠO `pages/components/BacktestPanel.tsx` (<200 dòng): chọn model (v1/v2) + grade + alpha;
  thẻ metric (MAPE, MAE, RMSE, % đúng hướng, n); chart; bảng per-lần; so v1 vs v2.
- SỬA `pages/FloorSuggestPage.tsx`: nhúng `BacktestPanel`; bảng gợi ý dùng model đã chọn.

## Phase 3 — Test & kiểm chứng
**Files**: TẠO `apps/api/tests/test_floor_suggest.py`
- `ridge_fit` khớp đáp án trên dữ liệu tổng hợp đã biết.
- **No-leakage**: backtest tại lần i KHÔNG đổi khi nối thêm dữ liệu tương lai (chống look-ahead).
- metrics/hit_rate đúng công thức.
- Endpoint `/backtest`, `/backtest/summary` qua TestClient.
- Kiểm chứng thực: chạy backtest v1 vs v2 trên DB, xác nhận v2 MAPE ≤ v1 cho SVR 10.

## Tiêu chí hoàn thành
- [x] Backtest toàn chuỗi (22 lần) trả MAPE/MAE/RMSE + % đúng hướng cho từng grade.
- [x] Sửa look-ahead: test no-leakage pass.
- [x] Màn web hiển thị metric + chart predicted-vs-actual + bảng + so v1/v2.
- [x] `uv run pytest` xanh (18/18); `pnpm build` xanh.

## KẾT QUẢ THỰC (đào sâu — quan trọng)
Đã đo bằng harness trên **cùng tập điểm**, qua 3 vòng thí nghiệm:
- **v1 (rổ 4 futures, đơn biến) là TỐT NHẤT**: MAPE 1.9% (12 lần gần đây) / 3.7% (toàn 22 lần),
  đúng hướng 88.9%. Vượt mục tiêu đề án ≤6%.
- v2 đa biến ridge + mủ nước: MAPE 3.73%, hit 86.7% — **KHÔNG cải thiện** (overfit trên n≈30).
- Đưa mủ nước vào rổ: MAPE 4.43% — tệ hơn. Mô hình Δ: hit 72% — tệ hơn.
- Giá mủ nước r=0.92 chỉ là tương quan *cùng xu hướng* (spurious), không thêm sức dự báo OOS.
→ **Quyết định**: giữ **v1 làm mặc định** (khuyến nghị); v2 để đối chiếu minh bạch.
→ Giá trị thật giao được: (1) **sửa look-ahead** → số liệu độ khớp đáng tin; (2) **harness backtest**
  ngăn ship model tệ hơn + làm bằng chứng chọn model cho lãnh đạo VRG.

## Todo
- [x] Phase 1 — backend model + backtest (numpy, causal, ridge, walk-forward)
- [x] Phase 2 — frontend kiểm định (BacktestPanel + BacktestChart)
- [x] Phase 3 — test (no-leakage, metrics, endpoint) + kiểm chứng v1>v2 trên DB thực
