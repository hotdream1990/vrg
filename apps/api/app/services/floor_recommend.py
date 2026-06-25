"""Lớp 'đề xuất điều chỉnh giá sàn': biến dự báo mức giá thành khuyến nghị NÂNG/GIỮ/HẠ
so với lần ban hành liền trước + bằng chứng (drivers thị trường, độ tin cậy backtest,
đối chiếu SHFE). THUẦN HÀM — không chạm DB; [floor_suggest.py] nạp dữ liệu rồi gọi vào đây.
"""
from __future__ import annotations

from typing import Any, Callable

from app.services import floor_model as fm

_CONF_DOWN = {"high": "medium", "medium": "low", "low": "low"}  # hạ tin cậy khi SHFE ngược hướng
_SHFE_MIN = 0.5   # |%biến động SHFE| tối thiểu để tính là xác nhận/ngược hướng (lọc nhiễu phẳng)


def prev_floor(fd: list[str], fmap: dict, grade: str, as_of: str) -> tuple[str | None, float | None]:
    """Giá sàn `grade` ở lần ban hành CÓ GIÁ gần nhất TRƯỚC as_of (None nếu không có)."""
    for d in reversed([x for x in fd if x < as_of]):
        v = fmap.get((d, grade))
        if v is not None:
            return d, float(v)
    return None, None


def drivers(idx: dict, keys: list[tuple[str, str]], labels: dict,
            at: Callable, prev_d: str | None, as_of: str) -> list[dict[str, Any]]:
    """Mức biến động từng chỉ số trong rổ kể từ lần ban hành trước → căn cứ cho đề xuất."""
    out = []
    for k in keys:
        cur = at(idx.get(k, []), as_of)
        prev = at(idx.get(k, []), prev_d) if prev_d else None
        chg = round((cur - prev) / prev * 100, 2) if (cur and prev) else None
        out.append({"index": labels[k], "prev": round(prev, 1) if prev is not None else None,
                    "cur": round(cur, 1) if cur is not None else None, "change_pct": chg})
    return out


def build_item(grade: str, act: float | None, sug: float | None, r: dict | None,
               prev: float | None, bt: dict, shfe_chg: float | None) -> dict[str, Any]:
    """Ghép 1 dòng đề xuất: Δ so lần trước, hành động (dead-band), độ tin cậy, cảnh báo SHFE.

    Dead-band = MAE backtest: |Δ| ≤ band ⇒ GIỮ (nhiễu). Hạ tin cậy + đánh dấu 'shfe_opposite'
    khi đề xuất nâng/hạ nhưng SHFE (chỉ báo dẫn hướng ~88%) đi ngược chiều rõ rệt.
    """
    delta = round(sug - prev) if (sug is not None and prev is not None) else None
    band = round(bt.get("mae") or 0.0)
    action = fm.decide_action(delta, band)
    # Khi đề xuất điều chỉnh ⇒ chấm tin cậy theo sai số trên CHÍNH các lần điều chỉnh
    # (mape_move), không lấy MAPE gộp (bị các lần giữ-nguyên kéo xuống giả tạo).
    mape_move, n_move = bt.get("mape_move"), bt.get("n_move", 0)
    rel_mape = mape_move if (action in ("raise", "lower") and n_move >= 3 and mape_move is not None) \
        else bt.get("mape")
    conf = fm.confidence(rel_mape, bt.get("hit"), bt.get("n", 0))
    caution = None
    if action in ("raise", "lower") and shfe_chg is not None and abs(shfe_chg) >= _SHFE_MIN \
            and (delta > 0) != (shfe_chg > 0):
        conf, caution = _CONF_DOWN[conf], "shfe_opposite"
    return {
        "grade": grade, "actual": act, "suggested": sug,
        "diff": (round(act - sug) if act is not None and sug is not None else None),
        "r": r["r"] if r else None,
        "prev": round(prev) if prev is not None else None, "delta": delta,
        "delta_pct": (round(delta / prev * 100, 1) if (delta is not None and prev) else None),
        "band": band, "action": action, "confidence": conf, "caution": caution,
        "mape": bt.get("mape"), "mape_move": mape_move, "n_move": n_move,
        "hit": bt.get("hit"), "n_bt": bt.get("n", 0),
    }
