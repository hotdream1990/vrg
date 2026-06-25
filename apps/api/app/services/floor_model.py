"""Mô hình hồi quy giá sàn: ridge đa biến (numpy) + chỉ số đánh giá độ khớp.

Tách riêng đại số tuyến tính & metric khỏi orchestration ([floor_suggest.py]).
NGUYÊN TẮC CAUSAL: mean/sd chuẩn hoá CHỈ tính trên tập train → tránh look-ahead bias
khi backtest (không để dữ liệu tương lai rò rỉ vào lúc fit).
"""
from __future__ import annotations

import numpy as np


def standardize(x_train: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Trả (mean, sd) theo cột trên train; sd==0 -> 1 để tránh chia 0."""
    mean = x_train.mean(axis=0)
    sd = x_train.std(axis=0)
    sd = np.where(sd == 0, 1.0, sd)
    return mean, sd


def ridge_fit(x: np.ndarray, y: np.ndarray, alpha: float) -> tuple[float, np.ndarray]:
    """Hồi quy ridge CÓ hệ số chặn (không phạt intercept). alpha=0 ⇒ OLS thường.

    x: (n,k) đã chuẩn hoá; y: (n,). Giải (XᵀX + αI)β = Xᵀy. Trả (intercept, beta[k]).
    """
    n, k = x.shape
    xb = np.hstack([np.ones((n, 1)), x])  # cột 1 cho intercept
    pen = np.eye(k + 1) * alpha
    pen[0, 0] = 0.0  # KHÔNG phạt intercept
    beta = np.linalg.solve(xb.T @ xb + pen, xb.T @ y)
    return float(beta[0]), beta[1:]


def predict(intercept: float, beta: np.ndarray, x_std: np.ndarray) -> float:
    return float(intercept + float(np.dot(beta, x_std)))


def metrics(actual: list[float], pred: list[float]) -> dict[str, float] | None:
    """MAE, MAPE(%), RMSE, R² out-of-sample. actual phải > 0 (giá sàn)."""
    if not actual:
        return None
    a = np.asarray(actual, float)
    p = np.asarray(pred, float)
    err = p - a
    ss_tot = float(np.sum((a - a.mean()) ** 2)) or 1.0
    return {
        "mae": round(float(np.mean(np.abs(err))), 1),
        "mape": round(float(np.mean(np.abs(err / a)) * 100), 2),
        "rmse": round(float(np.sqrt(np.mean(err ** 2))), 1),
        "r2": round(1 - float(np.sum(err ** 2)) / ss_tot, 3),
        "n": len(a),
    }


def hit_rate(actual: list[float], pred: list[float]) -> float | None:
    """% lần đoán đúng HƯỚNG điều chỉnh so với giá sàn lần liền trước.

    So sign(pred[t] - actual[t-1]) với sign(actual[t] - actual[t-1]) — đúng câu hỏi
    quyết định "nên nâng/hạ giá sàn so với lần đã ban hành gần nhất". Bỏ lần đi ngang.
    """
    if len(actual) < 2:
        return None
    a = np.asarray(actual, float)
    p = np.asarray(pred, float)
    prev = a[:-1]
    da = np.sign(a[1:] - prev)
    dp = np.sign(p[1:] - prev)
    valid = da != 0
    if not valid.any():
        return None
    return round(float(np.mean(da[valid] == dp[valid]) * 100), 1)


# --------------------- Luật quyết định điều chỉnh giá sàn ---------------------


def decide_action(delta: float | None, band: float) -> str | None:
    """NÂNG/GIỮ/HẠ theo dead-band: |Δ| ≤ band (= sai số trung bình mô hình) ⇒ 'hold'.

    Mục đích: không điều chỉnh giá sàn theo dao động nhỏ hơn chính sai số của mô hình
    (chỉ là nhiễu). Vượt ngưỡng mới coi là tín hiệu thực để nâng/hạ.
    """
    if delta is None:
        return None
    if abs(delta) <= band:
        return "hold"
    return "raise" if delta > 0 else "lower"


def confidence(mape: float | None, hit: float | None, n: int) -> str:
    """Độ tin cậy của đề xuất theo độ khớp backtest của grade: high/medium/low.

    Cao: MAPE ≤ 6% (đạt mục tiêu đề án) + đúng hướng ≥ 70% + ≥ 8 lần kiểm định.
    Thấp: MAPE > 10% hoặc quá ít lần kiểm định (n < 6) — không đủ bằng chứng.
    """
    if mape is None or n < 6:
        return "low"
    if mape <= 6 and (hit is None or hit >= 70) and n >= 8:
        return "high"
    if mape <= 10:
        return "medium"
    return "low"
