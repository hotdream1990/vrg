"""Engine gợi ý giá sàn Tập đoàn + backtest toàn chuỗi (màn 'Gợi ý giá sàn').

Hai mô hình dùng chung 1 đường fit (chuẩn hoá CAUSAL — chỉ trên train, xem [floor_model.py]):
  - v1: hồi quy ĐƠN BIẾN theo rổ (TB z-score của 4 chỉ số futures) — baseline đã sửa look-ahead.
  - v2: hồi quy ĐA BIẾN ridge trên [giá mủ nước + 4 futures] — chọn feature động theo độ phủ train.
Mức đề xuất NEO theo lần ban hành trước: giá sàn lần đó + mức mô hình thay đổi giữa hai ngày
(xem `_fit_at`), làm tròn theo bước giá ban hành (`floor_recommend.to_step`).
`backtest()` chạy walk-forward toàn bộ lần ban hành để đo độ khớp dự báo vs giá sàn thực tế.
"""
from __future__ import annotations

from bisect import bisect_right
from operator import itemgetter
import sys
from typing import Any

import numpy as np
from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import VRG_DOMESTIC_ONLY_GRADES, VRG_FLOOR_GRADES
from app.core.paths import bulletin_dir
from app.services import floor_model as fm
from app.services import floor_recommend as fr
from app.services import inventory_daily
from app.services.unit_series_stock import MIN_COVERAGE_RATIO, STOCK_START

_BULLETIN = bulletin_dir()
if str(_BULLETIN) not in sys.path:
    sys.path.insert(0, str(_BULLETIN))

from bulletin.convert import r0  # noqa: E402 - 1 nguồn làm tròn nửa-lên dùng chung

# Feature cho engine: mủ nước (mạnh nhất, r≈0.92) + 4 futures/physical nền.
FEATS = [("vrg", "mu_nuoc"), ("lgm", "SMR20"), ("sgx", "TSR20"), ("shfe", "RU"), ("tocom", "RSS3")]
LABELS = {("vrg", "mu_nuoc"): "Giá mủ nước", ("lgm", "SMR20"): "MRB SMR20",
          ("sgx", "TSR20"): "SGX TSR20", ("shfe", "RU"): "SHFE RU", ("tocom", "RSS3"): "OSE RSS3"}
# chỉ số tham chiếu thêm cho bảng tương quan (không vào model)
REF = {("reuters", "SMR20"): "Physical SMR20", ("lgm", "SMRCV"): "MRB SMRCV", ("sgx", "RSS3"): "SGX RSS3"}
# Tồn kho lấy THEO NGÀY từ biểu Tồn kho đơn vị (`inventory_daily`, có số từ 24/07/2026) — bỏ chuỗi
# tuần `fact_inventory` (chốt 24/09/2026). Lịch sử ngắn nên v1i/v1f chỉ chạy khi đủ lần ban hành có số.
INV = ("vrg", "ton_kho")     # tổng tồn kho — biến phụ cho "v1i" (rổ + tồn kho)
FREE = ("vrg", "ton_free")   # tồn kho TỰ DO = tồn kho − đã có HĐ (chưa bán) — cho "v1f"
LABELS[INV] = "Tồn kho"
LABELS[FREE] = "Tồn kho tự do (chưa có HĐ)"
EXTRA = {INV, FREE}          # biến phụ: giữ cột riêng, KHÔNG gộp vào rổ futures

PARTIAL_LOOKBACK = 14  # số ngày có giá đứng trước, dùng làm mốc "bình thường có mấy đơn vị nhập"
#: Mô hình khuyến nghị: đa biến + mủ nước thắng rổ 4 futures khi backtest trên prod 83 lần ban hành
#: 01/2024 → 09/2026 (theo mức: MAPE TB 2,85% vs 3,41%; sau khi neo lần trước 24/09/2026: 1,84% vs
#: 1,99%) — kết luận "v1 tốt nhất" hồi 06/2026 là trên n≈30, nay lật. Màn, API, tờ trình, Trợ lý AI dùng chung.
DEFAULT_MODEL = "v2"
MIN_TRAIN = 8     # tối thiểu số lần trong tập train để fit
MIN_COVER = 5     # 1 feature chỉ được dùng khi có >= ngần này điểm phủ trên train
DEFAULT_ALPHA = 1.0
LEAD = ("shfe", "RU")          # chỉ báo dẫn hướng (đồng hướng giá sàn ~88% lịch sử)


def _point(series: list[tuple[str, float]], d: str) -> tuple[str, float] | None:
    """(ngày, giá trị) của điểm gần nhất <= ngày d (series đã sort tăng theo ngày).

    Trả kèm ngày để nơi hiển thị nói được "OSE số ngày 18/09" khi sàn nghỉ nhiều phiên.
    Tìm NHỊ PHÂN: bản dò tuần tự bị gọi ~466.000 lần mỗi lượt gợi ý (backtest 14 chủng loại) và
    chiếm ~80% thời gian — prod 25/09/2026 (CPU QEMU) mất 11 giây một lượt.
    """
    i = bisect_right(series, d, key=itemgetter(0))
    return series[i - 1] if i else None


def _at(series: list[tuple[str, float]], d: str) -> float | None:
    """Giá trị gần nhất <= ngày d (series đã sort tăng theo ngày)."""
    p = _point(series, d)
    return p[1] if p else None


def _drop_partial_tail(rows: list[tuple[str, float, int]]) -> list[tuple[str, float]]:
    """Bỏ các ngày CUỐI mới vài đơn vị nhập giá mủ nước: bình quân khi đó đổi theo rổ đơn vị, không phải giá.

    Đo prod 24/09/2026: buổi sáng mới 1 đơn vị nhập (495) so với 7 đơn vị mọi ngày (bình quân 553,6)
    → mô hình đa biến đọc thành giá mủ nước giảm 10,6% và kéo đề xuất xuống. `rows` = (ngày, bình quân,
    số đơn vị) tăng theo ngày. Chỉ cắt ĐUÔI, so với số đơn vị nhiều nhất của các ngày có giá ngay trước
    đó — giữa chuỗi mà ít đơn vị là sự thật (03–04/2026 cả tháng chỉ 1 đơn vị nhập).
    """
    cut = len(rows)
    while cut > 1:
        before = [n for _, _, n in rows[max(0, cut - 1 - PARTIAL_LOOKBACK):cut - 1]]
        if rows[cut - 1][2] >= MIN_COVERAGE_RATIO * max(before):
            break
        cut -= 1
    return [(d, v) for d, v, _ in rows[:cut]]


def _target(grade: str, fob: float | None, dom: float | None) -> float | None:
    """Trị hồi quy của 1 grade: grade chỉ-nội-địa (SkimBlock) dùng VNĐ/T, còn lại dùng FOB USD/T."""
    v = dom if grade in VRG_DOMESTIC_ONLY_GRADES else fob
    return float(v) if v is not None else None


def _unit(grade: str) -> str:
    """Đơn vị của giá sàn grade để hiển thị (SkimBlock = VNĐ/T, còn lại = USD/T)."""
    return "VNĐ/T" if grade in VRG_DOMESTIC_ONLY_GRADES else "USD/T"


def _inv_need(model: str) -> str:
    """Phần tồn kho mô hình cần: v1f → tồn tự do, v1i → tổng, còn lại không dùng tồn kho."""
    return "full" if model == "v1f" else "total" if model == "v1i" else "none"


def _load(extra: tuple[str, ...] = (), snaps: inventory_daily.Snapshots | None = None,
          inv: str = "full") -> tuple:
    """Dữ liệu cho engine. `extra` = ngày cần thêm điểm tồn kho tự do (ngày gợi ý không phải lần ban hành);
    `snaps` = tồn kho ngày đã nạp sẵn (người gọi cần dùng lại cho ô chỉ số tồn kho).

    `inv` = phần tồn kho cần nạp: "none" · "total" (tổng, 1 lần quét biểu đơn vị) · "full" (+ tồn tự
    do, hỏi hợp đồng MỖI lần ban hành). Một lượt mở màn gọi hàm này ~7 lần song song — nạp thừa là
    nhân chi phí lên chừng ấy lần.
    """
    ensure_schema()
    with session_scope() as db:
        fr = db.execute(text("SELECT as_of, grade, fob_usd, domestic_vnd, lan FROM vrg_floor_price "
                             "ORDER BY as_of")).all()
        # price <> 0: phiên No Trading (sàn nghỉ/không ra settlement) không phải một mức giá —
        # để lọt vào rổ chỉ số là hồi quy trên một cú rơi về 0 không có thật.
        ir = db.execute(text("SELECT as_of, source, grade, price FROM fact_price "
                             "WHERE price_type IN ('settlement','physical') AND price <> 0 "
                             "ORDER BY as_of")).all()
        # price <> 0 (giống rổ chỉ số trên): đơn giá thu mua 0 = "không có giá", không phải một
        # mức giá — để lọt vào là bình quân ngày tụt hẳn và hồi quy học theo cú rơi không có thật.
        mr = db.execute(text("SELECT as_of, avg(price), count(*) FROM fact_price WHERE source='vrg' "
                             "AND price_type='purchase' AND price <> 0 "
                             "GROUP BY as_of ORDER BY as_of")).all()
    # fmap = trị hồi quy theo grade (FOB cho grade thường, VNĐ cho grade chỉ-nội-địa như SkimBlock).
    fmap = {(str(d), g): t for d, g, fob, dom, _ in fr
            if (t := _target(g, fob, dom)) is not None}
    floor_dates = sorted({d for d, _ in fmap})
    # Hiện ĐỦ danh mục chủng loại giá sàn theo thứ tự báo cáo (kể cả grade chưa có dữ liệu →
    # dòng trống); grade lạ trong dữ liệu (nếu có) xếp cuối theo ABC.
    data_grades = {g for _, g in fmap}
    grades = list(VRG_FLOOR_GRADES) + sorted(data_grades - set(VRG_FLOOR_GRADES))
    lanmap = {str(d): int(lan) for d, _, _, _, lan in fr}
    idx: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for d, s, g, v in ir:
        idx.setdefault((s, g), []).append((str(d), float(v)))
    idx[("vrg", "mu_nuoc")] = _drop_partial_tail([(str(d), float(v), int(n)) for d, v, n in mr])
    if inv != "none":
        snaps = inventory_daily.load() if snaps is None else snaps
        idx[INV] = inventory_daily.series(snaps)
    if inv == "full":
        # Tồn tự do cần hỏi hợp đồng từng ngày → chỉ tính tại các lần ban hành có số + ngày gợi ý.
        idx[FREE] = inventory_daily.free_series(snaps, [d for d in floor_dates if d >= STOCK_START] + list(extra))
    return floor_dates, grades, fmap, idx, lanmap


def _fit_at(train: list[str], target: str, grade: str, fmap: dict, idx: dict,
            model: str, alpha: float, shock: float = 0.0,
            anchor: tuple[str, float] | None = None) -> dict[str, Any] | None:
    """Fit trên `train`, dự báo giá sàn[grade] tại `target`. None nếu không đủ dữ liệu.

    `shock` = cú sốc % áp lên rổ chỉ số tại target (vd +0.05 = rổ tăng 5%) — dùng cho kịch bản.
    `anchor` = (ngày, giá sàn) của lần ban hành trước ⇒ `pred` = giá sàn lần đó + mức mô hình THAY
    ĐỔI giữa hai ngày (cùng một lần fit); không có ⇒ `pred` = mức mô hình. `level` luôn là mức mô hình.

    Vì sao neo: hồi quy theo MỨC mang theo phần lệch tồn đọng giữa mô hình và giá sàn Tập đoàn đã
    chọn. Đo prod 24/09/2026: 4 lần gần nhất mô hình cao hơn giá LATEX thực 9–15% trong khi Tập đoàn
    giữ nguyên ⇒ hôm nay "NÂNG LATEX +11,7%" dù rổ chỉ số gần như đứng yên. Backtest 83 lần, 14
    chủng loại: MAPE TB 2,85% (mức) → 1,84% (neo), đúng hướng 78% → 80%.
    """
    keys = (FEATS[1:] if model == "v1" else FEATS[1:] + [INV] if model == "v1i"
            else FEATS[1:] + [FREE] if model == "v1f" else FEATS)
    val = lambda k, d: _at(idx.get(k, []), d)  # noqa: E731
    need = [target] + ([anchor[0]] if anchor else [])   # neo cần đủ biến ở CẢ hai ngày
    sel = [k for k in keys
           if sum(val(k, d) is not None for d in train) >= MIN_COVER
           and all(val(k, d) is not None for d in need)]
    if not sel:
        return None
    # v1i/v1f mà thiếu tồn kho thì chỉ là v1 mang tên khác — trả None để màn so sánh không tưởng
    # "thêm tồn kho" cho kết quả y hệt rổ futures.
    if model in ("v1i", "v1f") and not EXTRA & set(sel):
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
    pooled = model in ("v1", "v1i", "v1f")  # gộp futures về 1 biến rổ; giữ biến phụ (tồn kho) riêng
    fut = [i for i, k in enumerate(sel) if k not in EXTRA]
    ext = [i for i, k in enumerate(sel) if k in EXTRA]

    def design(raw: np.ndarray) -> np.ndarray:
        """Giá trị gốc (n, k) → ma trận vào hồi quy (đã chuẩn hoá theo train; v1* gộp rổ)."""
        z = (raw - mean) / sd
        if not pooled:
            return z
        cols_ = [z[:, fut].mean(axis=1)] + ([z[:, ext[0]]] if ext else [])  # biến phụ: cột riêng
        return np.column_stack(cols_)

    point = lambda d, s=0.0: design(np.array([[val(k, d) for k in sel]], float) * (1 + s))[0]  # noqa: E731
    xs = design(x)
    a = 0.0 if pooled and not ext else alpha   # rổ đơn biến ⇒ OLS; có biến phụ ⇒ ridge nhẹ
    try:
        inter, beta = fm.ridge_fit(xs, y, a)
    except np.linalg.LinAlgError:  # ma trận suy biến (vd rổ hằng số) — bỏ lần này
        return None
    fit = inter + xs @ beta
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1.0
    r = max(0.0, 1 - float(np.sum((fit - y) ** 2)) / ss_tot) ** 0.5  # multiple-R train
    level = fm.predict(inter, beta, point(target, shock))
    pred = anchor[1] + level - fm.predict(inter, beta, point(anchor[0])) if anchor else level
    # Mức GIÁ SÀN (USD/T hoặc VNĐ/T) → làm tròn nửa LÊN như mọi số tiền.
    return {"pred": r0(pred), "level": r0(level), "n_train": len(rows),
            "feats": [LABELS[k] for k in sel], "r": round(r, 3)}


def points() -> list[dict[str, Any]]:
    """Danh sách lần đã ban hành (cho picker) — mới nhất trước.

    Kèm `title` (tiêu đề tự đặt) để picker hiển thị theo TEXT + ngày phát hành,
    thay cho số lần nội bộ (auto-increment) vốn không mang ý nghĩa với người dùng.
    """
    with session_scope() as db:
        rows = db.execute(text("SELECT lan, as_of, MAX(title) AS title FROM vrg_floor_price "
                               "GROUP BY lan, as_of ORDER BY as_of DESC")).mappings().all()
    return [{"lan": int(r["lan"]), "as_of": str(r["as_of"]),
             "title": (r["title"] or "").strip()} for r in rows]


def suggest(as_of: str, model: str = DEFAULT_MODEL, backtest: bool = True,
            alpha: float = DEFAULT_ALPHA) -> dict[str, Any]:
    """Đề xuất ĐIỀU CHỈNH giá sàn tại 1 lần: dự báo mức giá + so lần trước → NÂNG/GIỮ/HẠ.

    Mỗi grade ghép qua [floor_recommend.build_item]: dead-band = MAE backtest (|Δ| trong ngưỡng
    nhiễu ⇒ giữ nguyên), độ tin cậy theo độ khớp backtest, cảnh báo khi SHFE đi ngược hướng.
    backtest=True ⇒ chỉ fit data TRƯỚC as_of (so sánh khách quan với giá đã ban hành).
    """
    snaps = inventory_daily.load()
    fd, grades, fmap, idx, lanmap = _load((as_of,), snaps, "full" if model == "v1f" else "total")
    is_issuance = as_of in fd
    if not is_issuance:
        # Ngày BẤT KỲ (chưa ban hành): fit toàn bộ lịch sử TRƯỚC as_of, không có giá thực để so.
        if not fd or as_of <= fd[0]:
            return {"as_of": as_of, "items": [], "error": f"Ngày phải sau lần ban hành đầu tiên ({fd[0] if fd else '—'})"}
        backtest = True
    train = [d for d in fd if d != as_of and (d < as_of if backtest else True)]
    prev_d = max((d for d in fd if d < as_of), default=None)
    keys = FEATS[1:] if model == "v1" else FEATS
    drivers = fr.drivers(idx, keys, LABELS, _point, prev_d, as_of)
    chgs = [d["change_pct"] for d in drivers if d["change_pct"] is not None]
    shfe_chg = next((d["change_pct"] for d in drivers if d["index"] == LABELS[LEAD]), None)

    inventory = inventory_daily.at(snaps, as_of, prev_d)
    lean = fr.inventory_lean(inventory)
    feats_used: set[str] = set()
    n_train = 0
    items = []
    for g in grades:
        pd_, prev = fr.prev_floor(fd, fmap, g, as_of)
        r = _fit_at(train, as_of, g, fmap, idx, model, alpha,
                    anchor=(pd_, prev) if prev is not None else None)
        sug = fr.to_step(r["pred"], _unit(g)) if r else None
        if r:
            feats_used.update(r["feats"])
            n_train = max(n_train, r["n_train"])
        bt = _backtest_core(fd, fmap, idx, lanmap, g, model, alpha)["metrics"]
        items.append(fr.build_item(g, fmap.get((as_of, g)), sug, r, prev, bt, shfe_chg, _unit(g),
                                   lean["direction"] if lean else None))
    return {
        "as_of": as_of, "model": model, "backtest": backtest, "is_issuance": is_issuance,
        "n_train": n_train, "feats": sorted(feats_used), "prev_as_of": prev_d,
        "basket_change_pct": round(sum(chgs) / len(chgs), 2) if chgs else None,
        "drivers": drivers, "items": items, "inventory": inventory, "inventory_lean": lean,
        "inventory_start": STOCK_START,
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


def scenarios(as_of: str, model: str = DEFAULT_MODEL, shock_pct: float | None = None,
              alpha: float = DEFAULT_ALPHA) -> dict[str, Any]:
    """Ma trận kịch bản Giảm/Cơ sở/Tăng: áp cú sốc ±shock lên rổ chỉ số rồi dự báo lại từng grade.

    shock mặc định = 1 độ lệch chuẩn biến động rổ giữa các lần ban hành (kịch bản 'thường gặp').
    """
    fd, grades, fmap, idx, _ = _load((as_of,), inv=_inv_need(model))
    train = [d for d in fd if d < as_of]
    if not train:
        return {"as_of": as_of, "items": [], "error": "Cần ít nhất 1 lần ban hành trước ngày này"}
    shock = (shock_pct / 100.0) if shock_pct else _basket_sigma(fd, idx, model)
    items = []
    for g in grades:
        pd_, prev = fr.prev_floor(fd, fmap, g, as_of)
        anchor = (pd_, prev) if prev is not None else None   # cùng cách neo với `suggest`
        preds = {}
        for key, s in (("base", 0.0), ("bull", shock), ("bear", -shock)):
            r = _fit_at(train, as_of, g, fmap, idx, model, alpha, shock=s, anchor=anchor)
            preds[key] = fr.to_step(r["pred"], _unit(g)) if r else None
        items.append({"grade": g, "unit": _unit(g),
                      "prev": round(prev) if prev is not None else None, **preds})
    return {"as_of": as_of, "model": model, "shock_pct": round(shock * 100, 1), "items": items}


def _backtest_core(fd: list[str], fmap: dict, idx: dict, lanmap: dict,
                   grade: str, model: str, alpha: float) -> dict[str, Any]:
    """Walk-forward expanding window: mỗi lần fit data TRƯỚC đó rồi dự báo, so với thực tế.

    Dự báo neo theo lần ban hành trước (như `suggest`) để sai số đo đúng thứ màn hình đang đề xuất.
    """
    pts = []
    for i in range(MIN_TRAIN, len(fd)):
        target = fd[i]
        act = fmap.get((target, grade))
        if act is None:
            continue
        pd_, prev = fr.prev_floor(fd, fmap, grade, target)
        r = _fit_at(fd[:i], target, grade, fmap, idx, model, alpha,
                    anchor=(pd_, prev) if prev is not None else None)
        if not r:
            continue
        fv = _at(idx.get(FREE, []), target)  # tồn kho tự do (chưa có HĐ) tại lần này
        pts.append({"as_of": target, "lan": lanmap.get(target, i + 1), "actual": round(act),
                    "pred": r["pred"], "prev": round(prev) if prev is not None else None,
                    "ton_free": round(fv) if fv is not None else None,
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


def backtest(grade: str = "SVR 10 / CSR 10", model: str = DEFAULT_MODEL, alpha: float = DEFAULT_ALPHA) -> dict[str, Any]:
    """Backtest 1 grade trên toàn bộ lịch sử ban hành (đo độ khớp dự báo vs giá sàn thực).

    Nạp đủ tồn kho cho MỌI mô hình: biểu đồ backtest vẽ thêm đường tồn tự do tại từng lần ban hành.
    """
    fd, grades, fmap, idx, lanmap = _load()
    if grade not in grades:
        return {"grade": grade, "error": "Không có grade này", "points": [], "metrics": {"n": 0}}
    return {**_backtest_core(fd, fmap, idx, lanmap, grade, model, alpha), "inventory_start": STOCK_START}


def backtest_summary(model: str = DEFAULT_MODEL, alpha: float = DEFAULT_ALPHA) -> list[dict[str, Any]]:
    """MAPE / % đúng hướng / n cho từng grade — SVR 10 / CSR 10 (mặt hàng PoC) đứng đầu."""
    fd, grades, fmap, idx, lanmap = _load(inv=_inv_need(model))
    head = "SVR 10 / CSR 10"
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
    fd, grades, fmap, idx, _ = _load(inv="total")  # tồn tự do chỉ có ở vài lần ban hành, không đủ 15 điểm
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
    fd, grades, fmap, idx, _ = _load(inv="none")  # chỉ vẽ FEATS, không dùng tồn kho
    keys = [("self", grade)] + FEATS
    names = {("self", grade): f"Giá sàn {grade}", **LABELS}
    series = []
    for k in keys:
        raw = [fmap.get((d, grade)) for d in fd] if k[0] == "self" else [_at(idx.get(k, []), d) for d in fd]
        base = next((v for v in raw if v), None)
        vals = [round(v / base * 100, 1) if (v and base) else None for v in raw]
        series.append({"name": names.get(k, f"{k[0]}:{k[1]}"), "values": vals})
    return {"labels": fd, "series": series}
