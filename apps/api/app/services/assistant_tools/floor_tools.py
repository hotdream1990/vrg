"""Gói "Giá sàn & tư vấn điều chỉnh" — lý do tồn tại chính của Trợ lý.

Giá sàn = giá bán TỐI THIỂU cho hợp đồng chuyến do Tập đoàn ban hành. Mọi con số ở đây là
GỢI Ý tham khảo; quyết định cuối thuộc Ban lãnh đạo — system prompt bắt buộc nhắc điều đó.
"""
from __future__ import annotations

from typing import Any

from app.services import floor_repo, floor_suggest, inventory_repo, price_repo
from app.services.assistant_tools._common import (
    clamp_days, cols, days_ago, dm, dmy, err, line, pct, table, today,
)

_ACTION = {"raise": "NÂNG", "lower": "HẠ", "hold": "GIỮ"}
_DEFAULT_GRADE = "SVR 10 / CSR 10"


def _schedule_items(lan: int) -> dict[str, dict]:
    full = floor_repo.get_schedule(int(lan)) or {}
    return {it["grade"]: it for it in full.get("items", [])}


def _floor_prices(args: dict) -> dict:
    """Giá sàn của một lần ban hành (mặc định lần mới nhất) + chênh lệch so lần liền trước."""
    as_of = str(args.get("as_of") or "").strip()
    sched = floor_repo.list_schedules()
    if not sched:
        return err("Chưa có biểu giá sàn nào.")
    cur = next((s for s in sched if str(s["as_of"]) == as_of), None) if as_of else sched[0]
    if cur is None:
        return err(f"Không có lần ban hành nào áp dụng từ {dmy(as_of)}. "
                   f"Lần gần nhất: {dmy(sched[0]['as_of'])}.")
    i = sched.index(cur)
    prev = sched[i + 1] if i + 1 < len(sched) else None
    items = _schedule_items(cur["lan"])
    prev_items = _schedule_items(prev["lan"]) if prev else {}
    out = []
    for g, it in items.items():
        p = prev_items.get(g) or {}
        out.append({"grade": g, "fob_usd": it.get("fob_usd"), "domestic_vnd": it.get("domestic_vnd"),
                    "fob_lan_truoc": p.get("fob_usd"),
                    "thay_doi_pct": pct(it.get("fob_usd"), p.get("fob_usd"))})
    art = table(f"Giá sàn Tập đoàn · {cur['title']} (áp dụng {dmy(cur['as_of'])})",
                cols(("grade", "Chủng loại"), ("fob_usd", "FOB (USD/tấn)"),
                     ("domestic_vnd", "Nội địa (VNĐ/tấn)"), ("fob_lan_truoc", "FOB lần trước"),
                     ("thay_doi_pct", "Thay đổi %")), out)
    return {"summary": {"title": cur["title"], "as_of": str(cur["as_of"]),
                        "dispatch_no": cur.get("dispatch_no"),
                        "lan_truoc": dmy(prev["as_of"]) if prev else None,
                        "don_vi": "FOB = USD/tấn · Nội địa = VNĐ/tấn", "items": out},
            "artifact": art, "source": f"vrg_floor_price · {cur['title']} · {dmy(cur['as_of'])}"}


def _floor_history(args: dict) -> dict:
    """Lịch sử các lần ban hành: mức FOB của 1 chủng loại qua từng lần + biên độ điều chỉnh."""
    grade = str(args.get("grade") or _DEFAULT_GRADE).strip()
    limit = int(args.get("limit") or 12)
    sched = floor_repo.list_schedules()
    if not sched:
        return err("Chưa có biểu giá sàn nào.")
    picked = list(reversed(sched[:limit]))            # cũ → mới cho biểu đồ
    rows, values, labels = [], [], []
    prev_fob = None
    for s in picked:
        it = _schedule_items(s["lan"]).get(grade) or {}
        fob = it.get("fob_usd")
        rows.append({"ngay": dmy(s["as_of"]), "lan": s["title"], "fob_usd": fob,
                     "domestic_vnd": it.get("domestic_vnd"),
                     "thay_doi_pct": pct(fob, prev_fob)})
        if fob is not None:
            labels.append(dm(s["as_of"]))
            values.append(float(fob))
        prev_fob = fob if fob is not None else prev_fob
    if not values:
        return err(f"Chủng loại '{grade}' chưa có giá FOB trong các lần ban hành gần đây.")
    moves = [r["thay_doi_pct"] for r in rows if r["thay_doi_pct"] is not None]
    art = line(f"Giá sàn FOB {grade} qua {len(values)} lần ban hành", labels,
               [{"name": grade, "values": values}], "USD/tấn")
    return {"summary": {"grade": grade, "don_vi": "USD/tấn", "n_lan": len(rows),
                        "moi_nhat": values[-1], "cu_nhat": values[0],
                        "thay_doi_pct_toan_ky": pct(values[-1], values[0]),
                        "bien_do_tb_moi_lan_pct": round(sum(abs(m) for m in moves) / len(moves), 2)
                        if moves else None, "lich_su": rows},
            "artifact": art, "source": f"vrg_floor_price · {len(rows)} lần ban hành"}


def _suggest_floor(args: dict) -> dict:
    """Tư vấn NÂNG/GIỮ/HẠ từng chủng loại, kèm chỉ số dẫn hướng và bối cảnh tồn kho."""
    as_of = str(args.get("as_of") or today())
    try:
        s = floor_suggest.suggest(as_of)
    except Exception as exc:  # noqa: BLE001 - engine thiếu dữ liệu thì báo, đừng làm hỏng lượt hỏi
        return err(f"Không tính được gợi ý: {exc}")
    if s.get("error"):
        return err(s["error"])
    out = [{"grade": it["grade"], "hien_tai": it.get("prev"), "de_xuat": it.get("suggested"),
            "hanh_dong": _ACTION.get(it.get("action"), it.get("action")), "delta": it.get("delta"),
            "delta_pct": it.get("delta_pct"), "do_tin_cay": it.get("confidence")}
           for it in s.get("items", []) if it.get("suggested") is not None]
    if not out:
        return err(f"Chưa đủ dữ liệu để gợi ý giá sàn tại ngày {dmy(as_of)}.")
    art = table(f"Gợi ý điều chỉnh giá sàn ({dmy(as_of)})",
                cols(("grade", "Chủng loại"), ("hien_tai", "Giá hiện tại"), ("de_xuat", "Đề xuất"),
                     ("hanh_dong", "Hành động"), ("delta", "Δ"), ("delta_pct", "Δ%"),
                     ("do_tin_cay", "Độ tin cậy")), out)
    return {"summary": {
        "as_of": as_of, "lan_truoc": dmy(s.get("prev_as_of")),
        "basket_change_pct": s.get("basket_change_pct"),
        "drivers": [{"chi_so": d["index"], "thay_doi_pct": d["change_pct"]} for d in s.get("drivers", [])],
        "ton_kho": s.get("inventory"), "items": out,
        "note": "Hồi quy giá sàn theo rổ chỉ số; dead-band = MAE backtest (|Δ| nhỏ ⇒ GIỮ). "
                "Đây là GỢI Ý tham khảo, quyết định cuối thuộc Ban lãnh đạo."},
        "artifact": art, "source": f"engine gợi ý giá sàn · {dmy(as_of)}"}


def _scenarios(args: dict) -> dict:
    """Kịch bản Giảm/Cơ sở/Tăng: áp cú sốc ± lên rổ chỉ số rồi dự báo lại từng chủng loại."""
    as_of = str(args.get("as_of") or today())
    shock = args.get("shock_pct")
    try:
        s = floor_suggest.scenarios(as_of, shock_pct=float(shock) if shock else None)
    except Exception as exc:  # noqa: BLE001
        return err(f"Không dựng được kịch bản: {exc}")
    if s.get("error"):
        return err(s["error"])
    items = [it for it in s.get("items", []) if it.get("base") is not None]
    if not items:
        return err(f"Chưa đủ dữ liệu để dựng kịch bản tại ngày {dmy(as_of)}.")
    out = [{"grade": it["grade"], "don_vi": it.get("unit"), "hien_tai": it.get("prev"),
            "bear_giam": it.get("bear"), "base_co_so": it.get("base"), "bull_tang": it.get("bull")}
           for it in items]
    art = table(f"Kịch bản giá sàn ({dmy(as_of)}) · sốc rổ chỉ số ±{s.get('shock_pct')}%",
                cols(("grade", "Chủng loại"), ("hien_tai", "Hiện tại"), ("bear_giam", "Bear (giảm)"),
                     ("base_co_so", "Base (cơ sở)"), ("bull_tang", "Bull (tăng)"),
                     ("don_vi", "Đơn vị")), out)
    return {"summary": {"as_of": as_of, "shock_pct": s.get("shock_pct"), "items": out,
                        "note": "Cú sốc mặc định = 1 độ lệch chuẩn biến động rổ chỉ số giữa 2 lần ban hành."},
            "artifact": art, "source": f"engine kịch bản giá sàn · {dmy(as_of)}"}


# ── Tín hiệu bên lề cho việc ĐIỀU CHỈNH khỏi mức engine ──
# Trọng số = mức ảnh hưởng đo trên 80 lần ban hành (docs/project/tro-ly-ai-kha-nang.md):
# "mạnh" = dẫn dắt điều chỉnh; "bổ sung" = mang thông tin rổ futures KHÔNG có (tương quan riêng
# phần cao) — đây mới là thứ đáng dùng để lệch khỏi mức nền; "nền" = neo mặt bằng, không giải
# thích lần chỉnh này.
_W_STRONG, _W_EXTRA, _W_BASE = "mạnh", "bổ sung", "nền"


#: Dưới ngưỡng này coi như đi ngang — nhiễu, không đủ để lệch khỏi mức mô hình.
_FLAT_PCT = 0.5


def _signal(name: str, change_pct: float | None, weight: str, sign: int, note: str = "") -> dict:
    """1 dòng tín hiệu, ĐÃ QUY RA HƯỚNG cuối cùng.

    `sign` = +1 nếu tín hiệu thuận chiều giá sàn (tăng ⇒ hỗ trợ nâng), −1 nếu nghịch chiều
    (vd tồn kho: tồn TĂNG ⇒ áp lực bán ⇒ hỗ trợ HẠ).

    Vì sao phải tính sẵn: đo thực tế cho thấy để LLM tự nhân dấu là nó đọc nhầm — tồn kho GIẢM
    13,7% từng bị diễn giải thành "tồn kho cao nên nghiêng về giữ". Trả thẳng kết luận hướng thì
    không còn chỗ cho suy luận sai dấu.
    """
    if change_pct is None:
        huong = "chưa đủ dữ liệu"
    elif abs(change_pct) < _FLAT_PCT:
        huong = "trung tính (đi ngang)"
    else:
        up = (change_pct > 0) == (sign > 0)
        huong = "hỗ trợ NÂNG" if up else "hỗ trợ HẠ"
    chieu = "thuận chiều giá sàn" if sign > 0 else "nghịch chiều giá sàn"
    return {"tin_hieu": name, "thay_doi_pct": change_pct, "trong_so": weight,
            "huong_tac_dong": huong, "quan_he": chieu, "ghi_chu": note}


def _purchase_change(price_type: str, days: int) -> float | None:
    """Δ% giá thu mua bình quân Tập đoàn giữa nửa đầu và nửa cuối kỳ (lớp chuyên viên chốt)."""
    data = price_repo.purchase_prices_in_range(days_ago(days), today(), source="vrg")
    material = {"purchase": "latex", "purchase_cup": "cup"}[price_type]
    by_date: dict[str, list[float]] = {}
    for (_company, d), slots in data.items():
        v = slots.get(material)
        if v is not None:                       # giá 0 đã bị repo loại: "không có giá" ≠ giá bằng 0
            by_date.setdefault(d, []).append(v)
    dates = sorted(by_date)
    if len(dates) < 4:
        return None
    half = len(dates) // 2
    avg = lambda ds: sum(sum(by_date[d]) / len(by_date[d]) for d in ds) / len(ds)  # noqa: E731
    return pct(avg(dates[half:]), avg(dates[:half]))


def _floor_context(args: dict) -> dict:
    """Gom TÍN HIỆU BÊN LỀ quanh một lần điều chỉnh: rổ futures, giá mủ nguyên liệu, tồn kho.

    Mục đích: cho phép điều chỉnh khỏi mức đề xuất của engine một cách CÓ CĂN CỨ — mỗi tín hiệu
    kèm hướng tác động và trọng số đã đo, thay vì để người/AI ước lượng cảm tính.
    """
    as_of = str(args.get("as_of") or today())
    days = clamp_days(args.get("days"), 30)
    try:
        s = floor_suggest.suggest(as_of)
    except Exception as exc:  # noqa: BLE001
        return err(f"Không lấy được bối cảnh: {exc}")
    if s.get("error"):
        return err(s["error"])

    signals: list[dict] = []
    for d in s.get("drivers", []):
        signals.append(_signal(d["index"], d.get("change_pct"), _W_STRONG, +1))
    latex = _purchase_change("purchase", days)
    cup = _purchase_change("purchase_cup", days)
    if latex is not None:
        signals.append(_signal("Giá mủ nước (VRG chốt)", latex, _W_BASE, +1,
                               "NEO MẶT BẰNG — chỉ nói giá đang ở vùng nào, KHÔNG dùng để lệch khỏi mức mô hình"))
    if cup is not None:
        signals.append(_signal("Giá mủ chén (VRG chốt)", cup, _W_EXTRA, +1,
                               "mang thông tin nội địa mà rổ futures không có"))

    inv = s.get("inventory") or {}
    if inv.get("ton_kho") is not None:
        d_tk = inv.get("d_ton_kho")
        signals.append(_signal(
            f"Tồn kho Tập đoàn (tuần {dmy(inv.get('week'))})",
            pct(inv["ton_kho"], inv["ton_kho"] - d_tk) if d_tk is not None else None,
            _W_EXTRA, -1,  # tồn TĂNG ⇒ áp lực bán ⇒ hỗ trợ HẠ
            f"tồn {inv['ton_kho']:,.0f} tấn · tự do (chưa có HĐ) {inv.get('ton_free')} tấn"))

    # Cán cân CHỈ tính trên tín hiệu trọng số "bổ sung" — đó là phần duy nhất được phép làm lệch
    # mức mô hình (tín hiệu "mạnh" đã nằm trong mô hình, tín hiệu "nền" không nói về biên độ).
    extra = [g for g in signals if g["trong_so"] == _W_EXTRA]
    up = sum(1 for g in extra if g["huong_tac_dong"] == "hỗ trợ NÂNG")
    down = sum(1 for g in extra if g["huong_tac_dong"] == "hỗ trợ HẠ")
    balance = ("nghiêng NÂNG" if up > down else "nghiêng HẠ" if down > up
               else "cân bằng — giữ nguyên mức mô hình")
    weeks = len(inventory_repo.series(limit=8))
    return {"summary": {
        "as_of": as_of, "lan_truoc": dmy(s.get("prev_as_of")),
        "bien_dong_ro_chi_so_pct": s.get("basket_change_pct"),
        "can_can_tin_hieu_bo_sung": {"ho_tro_nang": up, "ho_tro_ha": down, "ket_luan": balance},
        "tin_hieu": signals, "so_tuan_ton_kho_co_du_lieu": weeks,
        "huong_dan": "Mức của engine đã tính từ rổ futures. Chỉ dùng tín hiệu trọng số 'bổ sung' "
                     "(giá mủ chén, tồn kho) và số liệu đơn vị thành viên để LỆCH khỏi mức đó; "
                     "tín hiệu 'mạnh' đã nằm trong mô hình rồi, đừng cộng thêm lần nữa. "
                     "Tín hiệu 'nền' chỉ dùng để nói giá đang ở vùng nào."},
        "artifact": table(f"Tín hiệu bối cảnh điều chỉnh giá sàn ({dmy(as_of)})",
                          cols(("tin_hieu", "Tín hiệu"), ("thay_doi_pct", "Thay đổi %"),
                               ("huong_tac_dong", "Hướng tác động"), ("trong_so", "Trọng số"),
                               ("ghi_chu", "Ghi chú")), signals),
        "source": f"engine drivers · fact_price (giá mủ NL) · fact_inventory · {dmy(as_of)}"}


TOOLS: dict[str, dict[str, Any]] = {
    "get_floor_prices": {
        "run": _floor_prices,
        "schema": {"name": "get_floor_prices",
                   "description": "Giá sàn Tập đoàn của một lần ban hành (mặc định lần MỚI NHẤT đang hiện hành) theo từng chủng loại: FOB USD/tấn, giá nội địa VNĐ/tấn, kèm mức lần trước và % thay đổi.",
                   "parameters": {"type": "object", "properties": {
                       "as_of": {"type": "string", "description": "ngày áp dụng YYYY-MM-DD của lần ban hành muốn xem (bỏ trống = lần mới nhất)"}}}}},
    "get_floor_history": {
        "run": _floor_history,
        "schema": {"name": "get_floor_history",
                   "description": "LỊCH SỬ ban hành giá sàn: mức FOB (USD/tấn) của một chủng loại qua N lần gần nhất, % thay đổi từng lần và biên độ điều chỉnh trung bình. Dùng khi hỏi 'các lần trước chỉnh bao nhiêu', 'giá sàn đã đi thế nào'.",
                   "parameters": {"type": "object", "properties": {
                       "grade": {"type": "string", "description": "chủng loại, vd 'SVR 10 / CSR 10' (mặc định), 'SVR 3L', 'LATEX'"},
                       "limit": {"type": "integer", "description": "số lần ban hành gần nhất (mặc định 12)"}}}}},
    "suggest_floor_adjustment": {
        "run": _suggest_floor,
        "schema": {"name": "suggest_floor_adjustment",
                   "description": "TƯ VẤN nên NÂNG/GIỮ/HẠ giá sàn từng chủng loại: mức đề xuất, Δ so lần trước, độ tin cậy, các chỉ số dẫn hướng (drivers) và bối cảnh tồn kho. Gọi tool này khi người dùng hỏi về điều chỉnh/khuyến nghị giá sàn.",
                   "parameters": {"type": "object", "properties": {
                       "as_of": {"type": "string", "description": "ngày YYYY-MM-DD (mặc định hôm nay)"}}}}},
    "simulate_floor_scenarios": {
        "run": _scenarios,
        "schema": {"name": "simulate_floor_scenarios",
                   "description": "KỊCH BẢN what-if giá sàn: nếu rổ chỉ số thị trường tăng/giảm X% thì mức giá sàn đề xuất là bao nhiêu (Bear/Base/Bull cho từng chủng loại). Dùng khi hỏi 'nếu thị trường giảm 5% thì sao'.",
                   "parameters": {"type": "object", "properties": {
                       "as_of": {"type": "string", "description": "ngày YYYY-MM-DD (mặc định hôm nay)"},
                       "shock_pct": {"type": "number", "description": "biên độ sốc % áp lên rổ chỉ số (bỏ trống = 1 độ lệch chuẩn lịch sử)"}}}}},
    "get_floor_context": {
        "run": _floor_context,
        "schema": {"name": "get_floor_context",
                   "description": "TÍN HIỆU BÊN LỀ quanh quyết định điều chỉnh giá sàn: biến động rổ chỉ số, giá mủ nguyên liệu (mủ nước · mủ chén), tồn kho Tập đoàn — mỗi tín hiệu kèm hướng tác động (thuận/nghịch) và TRỌNG SỐ đã đo. Gọi tool này SAU suggest_floor_adjustment khi cần điều chỉnh khỏi mức đề xuất của mô hình, để việc điều chỉnh có căn cứ thay vì cảm tính.",
                   "parameters": {"type": "object", "properties": {
                       "as_of": {"type": "string", "description": "ngày YYYY-MM-DD (mặc định hôm nay)"},
                       "days": {"type": "integer", "description": "số ngày tính biến động giá mủ nguyên liệu (mặc định 30)"}}}}},
}
