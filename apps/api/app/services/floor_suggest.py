"""Engine gợi ý giá sàn Tập đoàn + backtest toàn chuỗi (màn 'Gợi ý giá sàn').

Hai mô hình dùng chung 1 đường fit (chuẩn hoá CAUSAL — chỉ trên train, xem [floor_model.py]):
  - v1: hồi quy ĐƠN BIẾN theo rổ (TB z-score của 4 chỉ số futures) — baseline đã sửa look-ahead.
  - v2: hồi quy ĐA BIẾN ridge trên [giá mủ nước + 4 futures] — chọn feature động theo độ phủ train.
`backtest()` chạy walk-forward toàn bộ lần ban hành để đo độ khớp dự báo vs giá sàn thực tế.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import floor_model as fm
from app.services import floor_recommend as fr

# Feature cho engine: mủ nước (mạnh nhất, r≈0.92) + 4 futures/physical nền.
FEATS = [("vrg", "mu_nuoc"), ("lgm", "SMR20"), ("sgx", "TSR20"), ("shfe", "RU"), ("tocom", "RSS3")]
LABELS = {("vrg", "mu_nuoc"): "Giá mủ nước", ("lgm", "SMR20"): "MRB SMR20",
          ("sgx", "TSR20"): "SGX TSR20", ("shfe", "RU"): "SHFE RU", ("tocom", "RSS3"): "OSE RSS3"}
# chỉ số tham chiếu thêm cho bảng tương quan (không vào model)
REF = {("reuters", "SMR20"): "Physical SMR20", ("lgm", "SMRCV"): "MRB SMRCV", ("sgx", "RSS3"): "SGX RSS3"}
INV = ("vrg", "ton_kho")     # tổng tồn kho — biến phụ cho "v1i" (rổ + tồn kho)
FREE = ("vrg", "ton_free")   # tồn kho TỰ DO = tồn kho − đã có HĐ (chưa bán) — cho "v1f"
LABELS[INV] = "Tồn kho"
LABELS[FREE] = "Tồn kho tự do (chưa có HĐ)"
EXTRA = {INV, FREE}          # biến phụ: giữ cột riêng, KHÔNG gộp vào rổ futures

MIN_TRAIN = 8     # tối thiểu số lần trong tập train để fit
MIN_COVER = 5     # 1 feature chỉ được dùng khi có >= ngần này điểm phủ trên train
DEFAULT_ALPHA = 1.0
LEAD = ("shfe", "RU")          # chỉ báo dẫn hướng (đồng hướng giá sàn ~88% lịch sử)


def _at(series: list[tuple[str, float]], d: str) -> float | None:
    """Giá trị gần nhất <= ngày d (series đã sort tăng theo ngày)."""
    best = None
    for dd, v in series:
        if dd <= d:
            best = v
        else:
            break
    return best


def _load() -> tuple:
    ensure_schema()
    with session_scope() as db:
        fr = db.execute(text("SELECT as_of, grade, fob_usd, lan FROM vrg_floor_price "
                             "WHERE fob_usd IS NOT NULL ORDER BY as_of")).all()
        ir = db.execute(text("SELECT as_of, source, grade, price FROM fact_price "
                             "WHERE price_type IN ('settlement','physical') ORDER BY as_of")).all()
        mr = db.execute(text("SELECT as_of, avg(price) FROM fact_price WHERE source='vrg' "
                             "AND price_type='purchase' GROUP BY as_of ORDER BY as_of")).all()
        iv = db.execute(text("SELECT as_of, ton_kho, ton_kho_hd FROM fact_inventory "
                             "WHERE ton_kho IS NOT NULL ORDER BY as_of")).all()
    floor_dates = sorted({str(r[0]) for r in fr})
    grades = sorted({r[1] for r in fr})
    fmap = {(str(d), g): float(v) for d, g, v, _ in fr}
    lanmap = {str(d): int(lan) for d, _, _, lan in fr}
    idx: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for d, s, g, v in ir:
        idx.setdefault((s, g), []).append((str(d), float(v)))
    idx[("vrg", "mu_nuoc")] = [(str(d), float(v)) for d, v in mr]
    idx[INV] = [(str(d), float(v)) for d, v, _ in iv]
    idx[FREE] = [(str(d), float(v) - float(h)) for d, v, h in iv if h is not None]
    return floor_dates, grades, fmap, idx, lanmap


def _fit_at(train: list[str], target: str, grade: str, fmap: dict, idx: dict,
            model: str, alpha: float, shock: float = 0.0) -> dict[str, Any] | None:
    """Fit trên `train`, dự báo giá sàn[grade] tại `target`. None nếu không đủ dữ liệu.

    `shock` = cú sốc % áp lên rổ chỉ số tại target (vd +0.05 = rổ tăng 5%) — dùng cho kịch bản.
    """
    keys = (FEATS[1:] if model == "v1" else FEATS[1:] + [INV] if model == "v1i"
            else FEATS[1:] + [FREE] if model == "v1f" else FEATS)
    val = lambda k, d: _at(idx.get(k, []), d)  # noqa: E731
    sel = [k for k in keys
           if sum(val(k, d) is not None for d in train) >= MIN_COVER and val(k, target) is not None]
    if not sel:
        return None
    rows, ys = [], []
    for d in train:
        xs = [val(k, d) for k in sel]
        y = fmap.get((d, grade))
        if y is None or any(v is None for v in xs):
            continue
        rows.append(xs)
        ys.append(y)
    if len(rows) < max(MIN_TRAIN, len(sel) + 2):
        return None
    x = np.array(rows, float)
    y = np.array(ys, float)
    mean, sd = fm.standardize(x)
    xs = (x - mean) / sd
    xt = (np.array([val(k, target) for k in sel], float) * (1 + shock) - mean) / sd
    a = alpha
    if model in ("v1", "v1i", "v1f"):  # gộp futures về 1 biến rổ; giữ biến phụ (tồn kho) riêng
        fut = [i for i, k in enumerate(sel) if k not in EXTRA]
        ext = [i for i, k in enumerate(sel) if k in EXTRA]
        cols_s, cols_t = [xs[:, fut].mean(axis=1)], [xt[fut].mean()]
        if ext:  # biến phụ có phủ → thêm cột riêng (ridge nhẹ)
            cols_s.append(xs[:, ext[0]])
            cols_t.append(xt[ext[0]])
        xs = np.column_stack(cols_s)
        xt = np.array(cols_t)
        a = 0.0 if len(cols_s) == 1 else alpha
    try:
        inter, beta = fm.ridge_fit(xs, y, a)
    except np.linalg.LinAlgError:  # ma trận suy biến (vd rổ hằng số) — bỏ lần này
        return None
    fit = inter + xs @ beta
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1.0
    r = max(0.0, 1 - float(np.sum((fit - y) ** 2)) / ss_tot) ** 0.5  # multiple-R train
    return {"pred": round(fm.predict(inter, beta, xt)), "n_train": len(rows),
            "feats": [LABELS[k] for k in sel], "r": round(r, 3)}


def points() -> list[dict[str, Any]]:
    """Danh sách lần đã ban hành (cho picker) — mới nhất trước."""
    with session_scope() as db:
        rows = db.execute(text("SELECT lan, as_of FROM vrg_floor_price GROUP BY lan, as_of "
                               "ORDER BY as_of DESC")).all()
    return [{"lan": int(r[0]), "as_of": str(r[1])} for r in rows]


def suggest(as_of: str, model: str = "v1", backtest: bool = True,
            alpha: float = DEFAULT_ALPHA) -> dict[str, Any]:
    """Đề xuất ĐIỀU CHỈNH giá sàn tại 1 lần: dự báo mức giá + so lần trước → NÂNG/GIỮ/HẠ.

    Mỗi grade ghép qua [floor_recommend.build_item]: dead-band = MAE backtest (|Δ| trong ngưỡng
    nhiễu ⇒ giữ nguyên), độ tin cậy theo độ khớp backtest, cảnh báo khi SHFE đi ngược hướng.
    backtest=True ⇒ chỉ fit data TRƯỚC as_of (so sánh khách quan với giá đã ban hành).
    """
    fd, grades, fmap, idx, lanmap = _load()
    is_issuance = as_of in fd
    if not is_issuance:
        # Ngày BẤT KỲ (chưa ban hành): fit toàn bộ lịch sử TRƯỚC as_of, không có giá thực để so.
        if not fd or as_of <= fd[0]:
            return {"as_of": as_of, "items": [], "error": f"Ngày phải sau lần ban hành đầu tiên ({fd[0] if fd else '—'})"}
        backtest = True
    train = [d for d in fd if d != as_of and (d < as_of if backtest else True)]
    prev_d = max((d for d in fd if d < as_of), default=None)
    keys = FEATS[1:] if model == "v1" else FEATS
    drivers = fr.drivers(idx, keys, LABELS, _at, prev_d, as_of)
    chgs = [d["change_pct"] for d in drivers if d["change_pct"] is not None]
    shfe_chg = next((d["change_pct"] for d in drivers if d["index"] == LABELS[LEAD]), None)

    feats_used: set[str] = set()
    n_train = 0
    items = []
    for g in grades:
        r = _fit_at(train, as_of, g, fmap, idx, model, alpha)
        sug = r["pred"] if r else None
        if r:
            feats_used.update(r["feats"])
            n_train = max(n_train, r["n_train"])
        bt = _backtest_core(fd, fmap, idx, lanmap, g, model, alpha)["metrics"]
        _, prev = fr.prev_floor(fd, fmap, g, as_of)
        items.append(fr.build_item(g, fmap.get((as_of, g)), sug, r, prev, bt, shfe_chg))
    return {
        "as_of": as_of, "model": model, "backtest": backtest, "is_issuance": is_issuance,
        "n_train": n_train, "feats": sorted(feats_used), "prev_as_of": prev_d,
        "basket_change_pct": round(sum(chgs) / len(chgs), 2) if chgs else None,
        "drivers": drivers, "items": items,
    }


def _basket_sigma(fd: list[str], idx: dict, model: str) -> float:
    """Độ lệch chuẩn biến động % của rổ chỉ số giữa các lần ban hành liên tiếp (kẹp 3%–15%)."""
    keys = FEATS[1:] if model == "v1" else FEATS
    moves = []
    for a, b in zip(fd, fd[1:]):
        chs = [vb / va - 1 for k in keys
               if (va := _at(idx.get(k, []), a)) and (vb := _at(idx.get(k, []), b))]
        if chs:
            moves.append(sum(chs) / len(chs))
    if len(moves) < 3:
        return 0.05
    return float(min(max(np.std(moves), 0.03), 0.15))


def scenarios(as_of: str, model: str = "v1", shock_pct: float | None = None,
              alpha: float = DEFAULT_ALPHA) -> dict[str, Any]:
    """Ma trận kịch bản Giảm/Cơ sở/Tăng: áp cú sốc ±shock lên rổ chỉ số rồi dự báo lại từng grade.

    shock mặc định = 1 độ lệch chuẩn biến động rổ giữa các lần ban hành (kịch bản 'thường gặp').
    """
    fd, grades, fmap, idx, _ = _load()
    train = [d for d in fd if d < as_of]
    if not train:
        return {"as_of": as_of, "items": [], "error": "Cần ít nhất 1 lần ban hành trước ngày này"}
    shock = (shock_pct / 100.0) if shock_pct else _basket_sigma(fd, idx, model)
    items = []
    for g in grades:
        _, prev = fr.prev_floor(fd, fmap, g, as_of)
        preds = {}
        for key, s in (("base", 0.0), ("bull", shock), ("bear", -shock)):
            r = _fit_at(train, as_of, g, fmap, idx, model, alpha, shock=s)
            preds[key] = r["pred"] if r else None
        items.append({"grade": g, "prev": round(prev) if prev is not None else None, **preds})
    return {"as_of": as_of, "model": model, "shock_pct": round(shock * 100, 1), "items": items}


def _backtest_core(fd: list[str], fmap: dict, idx: dict, lanmap: dict,
                   grade: str, model: str, alpha: float) -> dict[str, Any]:
    """Walk-forward expanding window: mỗi lần fit data TRƯỚC đó rồi dự báo, so với thực tế."""
    pts = []
    for i in range(MIN_TRAIN, len(fd)):
        target = fd[i]
        act = fmap.get((target, grade))
        if act is None:
            continue
        r = _fit_at(fd[:i], target, grade, fmap, idx, model, alpha)
        if not r:
            continue
        prev = fr.prev_floor(fd, fmap, grade, target)[1]
        pts.append({"as_of": target, "lan": lanmap.get(target, i + 1), "actual": round(act),
                    "pred": r["pred"], "prev": round(prev) if prev is not None else None,
                    "err": round(r["pred"] - act),
                    "err_pct": round((r["pred"] - act) / act * 100, 2)})
    actual = [p["actual"] for p in pts]
    pred = [p["pred"] for p in pts]
    m = fm.metrics(actual, pred) or {"n": 0}
    m["hit"] = fm.hit_rate(actual, pred)
    # Sai số RIÊNG trên các lần mô hình thực sự đề xuất điều chỉnh (|pred-prev| > dead-band).
    # Tránh "thổi phồng" độ tin cậy bằng các lần giữ-nguyên dễ đoán.
    band = round(m.get("mae") or 0.0)
    mv = [p for p in pts if p["prev"] is not None and abs(p["pred"] - p["prev"]) > band]
    mm = fm.metrics([p["actual"] for p in mv], [p["pred"] for p in mv]) if mv else None
    m["mape_move"] = mm["mape"] if mm else None
    m["n_move"] = len(mv)
    return {"grade": grade, "model": model, "alpha": alpha, "metrics": m, "points": pts}


def backtest(grade: str = "SVR 10", model: str = "v1", alpha: float = DEFAULT_ALPHA) -> dict[str, Any]:
    """Backtest 1 grade trên toàn bộ lịch sử ban hành (đo độ khớp dự báo vs giá sàn thực)."""
    fd, grades, fmap, idx, lanmap = _load()
    if grade not in grades:
        return {"grade": grade, "error": "Không có grade này", "points": [], "metrics": {"n": 0}}
    return _backtest_core(fd, fmap, idx, lanmap, grade, model, alpha)


def backtest_summary(model: str = "v1", alpha: float = DEFAULT_ALPHA) -> list[dict[str, Any]]:
    """MAPE / % đúng hướng / n cho cả 13 grade — SVR 10 (mặt hàng PoC) đứng đầu."""
    fd, grades, fmap, idx, lanmap = _load()
    head = "SVR 10"
    ordered = ([head] if head in grades else []) + [g for g in grades if g != head]
    out = []
    for g in ordered:
        bt = _backtest_core(fd, fmap, idx, lanmap, g, model, alpha)
        m = bt["metrics"]
        out.append({"grade": g, "mape": m.get("mape"), "rmse": m.get("rmse"),
                    "hit": m.get("hit"), "n": m.get("n", 0)})
    return out


def correlation(grade: str) -> list[dict[str, Any]]:
    """Tương quan mức giá: 1 grade giá sàn vs từng chỉ số (Pearson), >=15 điểm."""
    fd, grades, fmap, idx, _ = _load()
    y = [fmap.get((d, grade)) for d in fd]
    out = []
    for k, name in {**LABELS, **REF}.items():
        x = [_at(idx.get(k, []), d) for d in fd]
        pts = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
        if len(pts) < 15:
            continue
        xa = np.array([p[0] for p in pts])
        ya = np.array([p[1] for p in pts])
        if xa.std() == 0 or ya.std() == 0:
            continue
        r = float(np.corrcoef(xa, ya)[0, 1])
        out.append({"index": name, "r": round(r, 3), "n": len(pts)})
    return sorted(out, key=lambda o: abs(o["r"]), reverse=True)


def chart(grade: str) -> dict[str, Any]:
    """Chuỗi giá sàn[grade] + chỉ số (chuẩn hoá base-100) để vẽ tương quan."""
    fd, grades, fmap, idx, _ = _load()
    keys = [("self", grade)] + FEATS
    names = {("self", grade): f"Giá sàn {grade}", **LABELS}
    series = []
    for k in keys:
        raw = [fmap.get((d, grade)) for d in fd] if k[0] == "self" else [_at(idx.get(k, []), d) for d in fd]
        base = next((v for v in raw if v), None)
        vals = [round(v / base * 100, 1) if (v and base) else None for v in raw]
        series.append({"name": names.get(k, f"{k[0]}:{k[1]}"), "values": vals})
    return {"labels": fd, "series": series}
