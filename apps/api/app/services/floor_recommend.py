"""Lớp 'đề xuất điều chỉnh giá sàn': biến dự báo mức giá thành khuyến nghị NÂNG/GIỮ/HẠ
so với lần ban hành liền trước + bằng chứng (drivers thị trường, độ tin cậy backtest,
đối chiếu SHFE). THUẦN HÀM — không chạm DB; [floor_suggest.py] nạp dữ liệu rồi gọi vào đây.
"""
from __future__ import annotations

import math
import sys
from typing import Any, Callable

from app.core.paths import bulletin_dir
from app.services import floor_model as fm

_BULLETIN = bulletin_dir()
if str(_BULLETIN) not in sys.path:
    sys.path.insert(0, str(_BULLETIN))

from bulletin.convert import r0, r1, r2  # noqa: E402 - 1 nguồn làm tròn nửa-lên dùng chung

_CONF_DOWN = {"high": "medium", "medium": "low", "low": "low"}  # hạ tin cậy khi có tín hiệu ngược hướng
_SHFE_MIN = 0.5   # |%biến động SHFE| tối thiểu để tính là xác nhận/ngược hướng (lọc nhiễu phẳng)
#: Tồn kho ngày dao động vài % là thường — dưới ngưỡng này coi là đi ngang, không cho nghiêng
#: (chủ dự án duyệt 24/09/2026). Dùng chung cho màn Gợi ý giá sàn, Trợ lý AI, đối chiếu giá tư nhân.
INVENTORY_LEAN_PCT = 3.0
#: Bước giá khi ban hành — đo prod (mọi lần ban hành từ 01/2025): 599/599 giá FOB là bội của 5 USD/T,
#: 644/644 giá nội địa là bội của 50.000 đồng. Đề xuất "2.353 USD/T" hay "62.014.747 đồng/tấn" không
#: phải một mức giá sàn ban hành được.
FOB_STEP = 5
VND_STEP = 50_000


def to_step(value: float | None, unit: str = "USD/T", how: str = "nearest") -> float | None:
    """Làm tròn mức giá sàn theo bước ban hành (`unit` "VNĐ/T" → 50.000, còn lại → 5 USD).

    `how`: "nearest" (nửa LÊN) · "up" · "down" — mép vùng dùng up/down để không rơi ra ngoài vùng.
    """
    if value is None:
        return None
    step = VND_STEP if unit == "VNĐ/T" else FOB_STEP
    q = value / step
    n = math.ceil(q) if how == "up" else math.floor(q) if how == "down" else r0(q)
    return n * step


def prev_floor(fd: list[str], fmap: dict, grade: str, as_of: str) -> tuple[str | None, float | None]:
    """Giá sàn `grade` ở lần ban hành CÓ GIÁ gần nhất TRƯỚC as_of (None nếu không có)."""
    for d in reversed([x for x in fd if x < as_of]):
        v = fmap.get((d, grade))
        if v is not None:
            return d, float(v)
    return None, None


def drivers(idx: dict, keys: list[tuple[str, str]], labels: dict,
            point: Callable, prev_d: str | None, as_of: str) -> list[dict[str, Any]]:
    """Mức biến động từng chỉ số trong rổ kể từ lần ban hành trước → căn cứ cho đề xuất.

    `point(series, ngày)` → (ngày có số, giá trị) | None. Kèm `cur_date`/`prev_date` = NGÀY CỦA SỐ
    thật sự dùng (sàn nghỉ lễ thì là phiên gần nhất trước đó) — không ghi ra là người đọc tưởng số
    của đúng ngày hỏi.
    """
    out = []
    for k in keys:
        cp = point(idx.get(k, []), as_of)
        pp = point(idx.get(k, []), prev_d) if prev_d else None
        cur, prev = (cp[1] if cp else None), (pp[1] if pp else None)
        chg = r2((cur - prev) / prev * 100) if (cur and prev) else None
        out.append({"index": labels[k], "prev": r1(prev) if prev is not None else None,
                    "cur": r1(cur) if cur is not None else None, "change_pct": chg,
                    "prev_date": pp[0] if pp else None, "cur_date": cp[0] if cp else None})
    return out


def inventory_lean(inv: dict[str, Any] | None) -> dict[str, Any] | None:
    """Tồn kho TỔNG + TỰ DO so với lần ban hành trước → tham chiếu nghiêng lên/xuống quanh mức mô hình.

    `direction`: "up" = tồn tăng (áp lực bán → nghiêng GIỮ/HẠ) · "down" = tồn giảm (nguồn chặt → ủng
    hộ NÂNG) · "flat" = cả hai trong ±`INVENTORY_LEAN_PCT` · "mixed" = tổng và tự do đi ngược nhau
    rõ rệt → không nghiêng. None = chưa có mốc so sánh. Chỉ là THAM CHIẾU: không sửa số mô hình —
    tồn kho ngày mới có từ 24/07/2026, chưa đủ lần ban hành để đưa vào hồi quy.
    """
    if not inv:
        return None
    total, free = inv.get("d_ton_kho_pct"), inv.get("d_free_pct")
    moves = [p for p in (total, free) if p is not None]
    if not moves:
        return None
    up = any(p >= INVENTORY_LEAN_PCT for p in moves)
    down = any(p <= -INVENTORY_LEAN_PCT for p in moves)
    direction = "mixed" if up and down else "up" if up else "down" if down else "flat"
    return {"direction": direction, "total_pct": total, "free_pct": free,
            "threshold_pct": INVENTORY_LEAN_PCT, "base_day": inv.get("base_day"), "day": inv.get("day")}


def build_item(grade: str, act: float | None, sug: float | None, r: dict | None,
               prev: float | None, bt: dict, shfe_chg: float | None,
               unit: str = "USD/T", lean: str | None = None) -> dict[str, Any]:
    """Ghép 1 dòng đề xuất: Δ so lần trước, hành động (dead-band), độ tin cậy, cảnh báo.

    Dead-band = MAE backtest: |Δ| ≤ band ⇒ GIỮ (nhiễu). Mỗi tín hiệu đi NGƯỢC đề xuất nâng/hạ thì
    hạ tin cậy 1 bậc + thêm vào `cautions`: 'shfe_opposite' (SHFE — chỉ báo dẫn hướng ~88% — đi ngược
    rõ rệt) · 'inventory_opposite' (`lean` = hướng tồn kho: nâng mà tồn tăng, hạ mà tồn giảm).
    `unit` = đơn vị giá sàn grade (USD/T, hoặc VNĐ/T cho grade chỉ-nội-địa như SkimBlock).
    """
    # Nửa LÊN: delta được so với dead-band để ra NÂNG/GIỮ/HẠ, lệch 1 USD ở sát mép là đổi
    # hẳn khuyến nghị — không để round() của Python (làm tròn về số chẵn) quyết định.
    delta = r0(sug - prev) if (sug is not None and prev is not None) else None
    band = r0(bt.get("mae") or 0.0)
    action = fm.decide_action(delta, band)
    # Khi đề xuất điều chỉnh ⇒ chấm tin cậy theo sai số trên CHÍNH các lần điều chỉnh
    # (mape_move), không lấy MAPE gộp (bị các lần giữ-nguyên kéo xuống giả tạo).
    mape_move, n_move = bt.get("mape_move"), bt.get("n_move", 0)
    rel_mape = mape_move if (action in ("raise", "lower") and n_move >= 3 and mape_move is not None) \
        else bt.get("mape")
    # Không có dự báo (grade chưa có dữ liệu giá sàn) → không có độ tin cậy để hiển thị.
    conf = fm.confidence(rel_mape, bt.get("hit"), bt.get("n", 0)) if sug is not None else None
    cautions: list[str] = []
    if action in ("raise", "lower") and shfe_chg is not None and abs(shfe_chg) >= _SHFE_MIN \
            and (delta > 0) != (shfe_chg > 0):
        conf = _CONF_DOWN[conf]
        cautions.append("shfe_opposite")
    if (action, lean) in (("raise", "up"), ("lower", "down")):
        conf = _CONF_DOWN[conf]
        cautions.append("inventory_opposite")
    return {
        "grade": grade, "unit": unit, "actual": act, "suggested": sug,
        "diff": (r0(act - sug) if act is not None and sug is not None else None),
        "r": r["r"] if r else None,
        "prev": r0(prev) if prev is not None else None, "delta": delta,
        "delta_pct": (r1(delta / prev * 100) if (delta is not None and prev) else None),
        "band": band, "action": action, "confidence": conf, "cautions": cautions,
        "mape": bt.get("mape"), "mape_move": mape_move, "n_move": n_move,
        "hit": bt.get("hit"), "n_bt": bt.get("n", 0),
    }
